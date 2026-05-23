"""NetSwitch - Windows 系统托盘网络配置切换工具"""

import sys
import os


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
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QSignalBlocker

import profile_manager
import network_controller
from tray import TrayIcon
from main_window import MainWindow
from settings_dialog import SettingsDialog


APP_NAME = "NetSwitch"
MUTEX_NAME = "Global_NetSwitch_SingleInstance"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


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
        self.tray.update_startup_state(self._is_startup_enabled())
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
        self.main_window = None

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
        dlg = SettingsDialog(self.config, parent=None)
        self._settings_dialog = dlg
        dlg.startup_toggled.connect(self._on_toggle_startup)
        try:
            dlg.exec()
        finally:
            self._settings_dialog = None

    def run(self):
        return self.app.exec()

    def quit(self):
        self.tray.hide()
        self.app.quit()


def main():
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
