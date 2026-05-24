"""NetSwitch - Windows 系统托盘网络配置切换工具"""

import sys
import os
import traceback
import subprocess
import tempfile
from pathlib import Path


def _read_version():
    """从 VERSION 文件读取版本号"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(base, "VERSION"), "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


__version__ = _read_version()
import ctypes
import ctypes.wintypes

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QSignalBlocker, QUrl
from PyQt6.QtGui import QDesktopServices

import profile_manager
import network_controller
import update_manager
from tray import TrayIcon
from main_window import MainWindow
from settings_dialog import SettingsDialog


APP_NAME = "NetSwitch"
MUTEX_NAME = "Global_NetSwitch_SingleInstance"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
HOMEPAGE_URL = "https://github.com/MoeMoeGit/NetSwitch"
ISSUES_URL = "https://github.com/MoeMoeGit/NetSwitch/issues"
RELEASES_URL = "https://github.com/MoeMoeGit/NetSwitch/releases/latest"


# ── 单实例检测 ──

def _try_bring_existing_window():
    """尝试将已有实例的窗口唤到前台"""
    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    GetWindowTextW = user32.GetWindowTextW
    SetForegroundWindow = user32.SetForegroundWindow
    ShowWindow = user32.ShowWindow

    SW_RESTORE = 9
    target_title = APP_NAME

    found = []
    GetWindowTextLengthW = user32.GetWindowTextLengthW

    def callback(hwnd, _lparam):
        length = GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            if target_title in buf.value:
                found.append(hwnd)
        return True

    EnumWindows(EnumWindowsProc(callback), 0)

    if found:
        hwnd = found[0]
        ShowWindow(hwnd, SW_RESTORE)
        SetForegroundWindow(hwnd)
        return True
    return False


def _log_uncaught_exception(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    try:
        network_controller._log_error(
            "uncaught exception:\n" + "".join(traceback.format_exception(exc_type, exc, tb)).rstrip()
        )
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)


def acquire_mutex():
    """获取全局 Mutex，返回 (mutex_handle, is_first_instance)"""
    kernel32 = ctypes.windll.kernel32
    CreateMutexW = kernel32.CreateMutexW
    GetLastError = kernel32.GetLastError

    ERROR_ALREADY_EXISTS = 183

    handle = CreateMutexW(None, True, MUTEX_NAME)
    if GetLastError() == ERROR_ALREADY_EXISTS:
        return handle, False
    return handle, True


# ── 管理员权限 ──

def _is_running_as_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin():
    if getattr(sys, 'frozen', False):
        executable = sys.executable
        params = ""
    else:
        executable = sys.executable
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{script}"'] + [f'"{arg}"' for arg in sys.argv[1:]])

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )
        return result > 32
    except Exception:
        return False


# ── 后台线程：托盘切换方案 ──

class _TrayApplyWorker(QThread):
    finished = pyqtSignal(str, str, str)  # profile_id, status, error_message

    def __init__(self, profile):
        super().__init__()
        self.profile = profile

    def run(self):
        status, error = network_controller.apply_profile(self.profile)
        self.finished.emit(self.profile["id"], status, error or "")


# ── 后台线程：网络状态检测 ──

class _StatusCheckWorker(QThread):
    finished = pyqtSignal(str, object, object)  # status, adapter_ip, gateway

    def run(self):
        adapter_ip = network_controller.get_default_adapter_ip()
        gateway = None

        if adapter_ip:
            gateway = network_controller.get_gateway(adapter_ip)
            if gateway and network_controller.ping(gateway):
                status = "normal"
            else:
                status = "warning"
        else:
            status = "warning"

        self.finished.emit(status, adapter_ip, gateway)


class _UpdateCheckWorker(QThread):
    finished = pyqtSignal(object, str)  # release dict or None, error

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            release = update_manager.get_latest_release(self.current_version)
            self.finished.emit(release, "")
        except Exception as e:
            self.finished.emit(None, str(e))


class _UpdateDownloadWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, str)  # installer_path, error

    def __init__(self, release):
        super().__init__()
        self.release = release

    def run(self):
        try:
            asset_name = self.release.get("asset_name") or "NetSwitch-Setup.exe"
            destination = Path(tempfile.gettempdir()) / asset_name

            def on_progress(downloaded, total):
                if total:
                    self.progress.emit(int(downloaded * 100 / total))

            path = update_manager.download_file(
                self.release.get("asset_url", ""),
                destination,
                progress_callback=on_progress,
            )
            self.finished.emit(path, "")
        except Exception as e:
            self.finished.emit("", str(e))


# ── 主应用 ──

class NetSwitchApp:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.config = profile_manager.load_config()

        # 托盘
        self.tray = TrayIcon()
        self.tray.profile_selected.connect(self._on_tray_profile_selected)
        self.tray.open_main_window.connect(self.show_main_window)
        self.tray.quit_app.connect(self.quit)
        self.tray.toggle_startup.connect(self._on_toggle_startup)
        self.tray.open_settings.connect(self._on_open_settings)
        self.tray.refresh_status_requested.connect(self._check_network_status)
        startup_enabled = self._is_startup_enabled()
        if profile_manager.get_start_with_windows(self.config) != startup_enabled:
            profile_manager.set_start_with_windows(self.config, startup_enabled)
        self.tray.update_startup_state(startup_enabled)
        self.tray.show()

        # 主界面（延迟创建）
        self.main_window = None
        self._settings_dialog = None
        self._last_network_snapshot = {
            "status": "warning",
            "ip": None,
            "gateway": None,
        }
        self._status_worker = None
        self._tray_worker = None
        self._is_switching = False
        self._update_check_worker = None
        self._update_download_worker = None
        self._pending_update_installer = None

        # 更新托盘（含开机自启状态）
        self._update_tray()

        # 开机恢复方案
        if self.config.get("restore_last_on_boot"):
            self._restore_last_profile()

        # 启动时执行一次网络状态检测，设置初始图标颜色
        QTimer.singleShot(0, self._check_network_status)

    def _update_tray(self):
        profiles = profile_manager.get_profiles(self.config)
        active_id = self.config.get("active_profile_id", "default")
        self.tray.update_profiles(profiles, active_id)

    def _check_network_status(self):
        active = profile_manager.get_active_profile(self.config)
        if not active:
            return

        if self._status_worker and self._status_worker.isRunning():
            return

        self._status_worker = _StatusCheckWorker()
        self._status_worker.finished.connect(self._on_status_check_finished)
        self._status_worker.start()

    def _on_status_check_finished(self, status, adapter_ip, gateway):
        self._last_network_snapshot = {
            "status": status,
            "ip": adapter_ip,
            "gateway": gateway,
        }
        self.tray.update_status(status)
        if self.main_window:
            self.main_window.update_network_snapshot(self._last_network_snapshot)
        self._status_worker = None

    def _restore_last_profile(self):
        active = profile_manager.get_active_profile(self.config)
        if active and active["id"] != "default":
            status, _ = network_controller.apply_profile(active)
            if status != network_controller.FAILED:
                profile_manager.update_last_used(self.config, active["id"])

    def _on_tray_profile_selected(self, profile_id):
        if (
            self._is_switching
            or (self._tray_worker and self._tray_worker.isRunning())
            or (self.main_window and self.main_window.is_applying())
            or network_controller._APPLY_LOCK.locked()
        ):
            return
        profile = profile_manager.get_profile_by_id(self.config, profile_id)
        if not profile:
            return

        self.tray.update_status("switching")
        self._is_switching = True

        self._tray_worker = _TrayApplyWorker(profile)
        self._tray_worker.finished.connect(self._on_tray_apply_finished)
        self._tray_worker.start()

    def _on_tray_apply_finished(self, profile_id, status, error):
        self._is_switching = False
        self._tray_worker = None

        try:
            if status == network_controller.FAILED:
                self.tray.update_status("error")
                if error:
                    self.tray.setToolTip(f"NetSwitch - 切换失败：{error}")
                if self.main_window:
                    self.main_window.set_network_status("error")
            else:
                profile_manager.set_active_profile(self.config, profile_id)
                profile_manager.update_last_used(self.config, profile_id)
                self._update_tray()
                if status == network_controller.GATEWAY_UNREACHABLE:
                    self.tray.update_status("warning")
                    if self.main_window:
                        self.main_window.set_network_status("warning")
                else:
                    self.tray.update_status("normal")
                    if self.main_window:
                        self.main_window.set_network_status("normal")
                self._check_network_status()
        except Exception as e:
            try:
                network_controller._log_error(f"tray apply finish exception: {e}")
                network_controller._log_error(
                    "".join(traceback.format_exception(type(e), e, e.__traceback__)).rstrip()
                )
            except Exception:
                pass
            QMessageBox.critical(None, APP_NAME, f"切换完成后处理失败：{e}")

    def show_main_window(self):
        if not self.main_window:
            self.main_window = MainWindow(self.config)
            self.main_window.profile_applied.connect(self._on_profile_applied)
            self.main_window.profile_saved.connect(self._on_profile_saved)
            self.main_window.window_closed.connect(self._on_window_closed)

        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self.main_window.update_network_snapshot(self._last_network_snapshot)
        self._check_network_status()

    def _on_profile_applied(self, profile_id):
        self._update_tray()
        self._check_network_status()

    def _on_profile_saved(self):
        self._update_tray()
        self._check_network_status()

    def _on_window_closed(self):
        pass

    @staticmethod
    def _get_exe_path():
        """获取当前 exe 路径（打包后为 exe 路径，开发时为脚本路径）"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        return os.path.abspath(sys.argv[0])

    def _set_start_with_windows(self, enabled):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE,
            )
            try:
                if enabled:
                    winreg.SetValueEx(
                        key, APP_NAME, 0, winreg.REG_SZ, f'"{self._get_exe_path()}"'
                    )
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            finally:
                winreg.CloseKey(key)
            return True, ""
        except Exception as e:
            return False, str(e)

    def _is_startup_enabled(self):
        """检查注册表中是否已设置开机自启"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ,
            )
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except (FileNotFoundError, OSError):
            return False

    def _on_toggle_startup(self, enabled):
        """托盘菜单切换开机自启"""
        success, message = self._set_start_with_windows(enabled)
        if success:
            profile_manager.set_start_with_windows(self.config, enabled)
            self.tray.update_startup_state(enabled)
            return

        current = profile_manager.get_start_with_windows(self.config)
        self.tray.update_startup_state(current)
        if self._settings_dialog and hasattr(self._settings_dialog, "chk_startup"):
            blocker = QSignalBlocker(self._settings_dialog.chk_startup)
            self._settings_dialog.chk_startup.setChecked(current)
            del blocker
        QMessageBox.warning(
            None,
            APP_NAME,
            f"开机自启设置失败：{message}",
        )

    def _on_open_settings(self):
        """打开设置弹窗"""
        dlg = SettingsDialog(self.config, version=__version__, parent=None)
        self._settings_dialog = dlg
        dlg.startup_toggled.connect(self._on_toggle_startup)
        dlg.check_update_requested.connect(self._on_check_update_requested)
        dlg.open_homepage_requested.connect(lambda: self._open_url(HOMEPAGE_URL))
        dlg.open_issues_requested.connect(lambda: self._open_url(ISSUES_URL))
        try:
            dlg.exec()
        finally:
            self._settings_dialog = None

    def _open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def _set_update_button_state(self, enabled, text):
        if self._settings_dialog and hasattr(self._settings_dialog, "btn_check_update"):
            self._settings_dialog.btn_check_update.setEnabled(enabled)
            self._settings_dialog.btn_check_update.setText(text)

    def _is_installed_version(self):
        exe_path = Path(self._get_exe_path()).resolve()
        return (
            exe_path.with_name("unins000.exe").exists()
            or exe_path.with_name("unins000.dat").exists()
        )

    def _on_check_update_requested(self):
        if self._is_network_switching():
            QMessageBox.information(None, APP_NAME, "正在切换网络，请完成后再检查更新。")
            return
        if not self._is_installed_version():
            QMessageBox.information(
                None,
                APP_NAME,
                "当前是便携版，内置自动更新仅支持已安装版本。请打开发布页手动下载新的便携版。",
            )
            self._open_url(RELEASES_URL)
            return
        if self._update_check_worker and self._update_check_worker.isRunning():
            return

        self._set_update_button_state(False, "正在检查…")
        self._update_check_worker = _UpdateCheckWorker(__version__)
        self._update_check_worker.finished.connect(self._on_update_check_finished)
        self._update_check_worker.start()

    def _on_update_check_finished(self, release, error):
        self._update_check_worker = None
        self._set_update_button_state(True, "检查更新")

        if error:
            network_controller._log_error(f"update check failed: {error}")
            QMessageBox.warning(None, APP_NAME, f"检查更新失败：{error}")
            return

        if not release:
            QMessageBox.information(None, APP_NAME, f"当前已是最新版本（{__version__}）。")
            return

        box = QMessageBox(None)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"发现新版本 {release['version']}")
        box.setInformativeText(
            f"当前版本：{__version__}\n"
            f"安装包：{release.get('asset_name', '')}\n\n"
            "可以直接下载安装包，也可以打开 GitHub Release 页面手动查看。"
        )
        if release.get("body"):
            box.setDetailedText(release["body"])
        download_btn = box.addButton("下载并安装", QMessageBox.ButtonRole.AcceptRole)
        open_btn = box.addButton("打开发布页", QMessageBox.ButtonRole.ActionRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == download_btn:
            self._download_update(release)
        elif clicked == open_btn:
            self._open_url(release.get("html_url") or HOMEPAGE_URL)

    def _download_update(self, release):
        if self._is_network_switching():
            QMessageBox.information(None, APP_NAME, "正在切换网络，请完成后再安装更新。")
            return
        if not self._is_installed_version():
            QMessageBox.information(
                None,
                APP_NAME,
                "当前是便携版，不能在运行中自动安装更新。请打开发布页手动下载新的便携版。",
            )
            self._open_url(RELEASES_URL)
            return
        if self._update_download_worker and self._update_download_worker.isRunning():
            return
        if not release.get("asset_url"):
            QMessageBox.warning(None, APP_NAME, "更新安装包下载地址无效。")
            return

        self._set_update_button_state(False, "正在下载…")
        self._update_download_worker = _UpdateDownloadWorker(release)
        self._update_download_worker.progress.connect(self._on_update_download_progress)
        self._update_download_worker.finished.connect(self._on_update_download_finished)
        self._update_download_worker.start()

    def _on_update_download_progress(self, percent):
        self._set_update_button_state(False, f"正在下载 {percent}%")

    def _on_update_download_finished(self, installer_path, error):
        self._update_download_worker = None
        self._set_update_button_state(True, "检查更新")

        if error:
            network_controller._log_error(f"update download failed: {error}")
            QMessageBox.warning(None, APP_NAME, f"下载更新失败：{error}")
            return

        if self._is_network_switching():
            QMessageBox.information(None, APP_NAME, "更新已下载。请等待网络切换完成后，再重新点击检查更新安装。")
            return

        reply = QMessageBox.question(
            None,
            APP_NAME,
            "更新安装包已下载。是否现在退出 NetSwitch 并运行安装程序？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._pending_update_installer = installer_path
            self.quit()

    def run(self):
        return self.app.exec()

    def _is_network_switching(self):
        return (
            self._is_switching
            or (self._tray_worker and self._tray_worker.isRunning())
            or (self.main_window and self.main_window.is_applying())
            or network_controller._APPLY_LOCK.locked()
        )

    def quit(self):
        installer = self._pending_update_installer
        if installer:
            try:
                subprocess.Popen(
                    [installer],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as e:
                network_controller._log_error(f"launch installer failed: {e}")
                QMessageBox.warning(None, APP_NAME, f"启动安装程序失败：{e}")
                self._pending_update_installer = None
                return
        self.tray.hide()
        self.app.quit()


def main():
    sys.excepthook = _log_uncaught_exception
    if not _is_running_as_admin():
        if _relaunch_as_admin():
            sys.exit(0)
        try:
            from PyQt6.QtWidgets import QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                APP_NAME,
                "NetSwitch 需要管理员权限才能修改网络配置。",
            )
        except Exception:
            pass
        sys.exit(1)

    # 单实例检测
    mutex_handle, is_first = acquire_mutex()
    if not is_first:
        _try_bring_existing_window()
        sys.exit(0)

    try:
        app = NetSwitchApp()
        sys.exit(app.run())
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
