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

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

import profile_manager
import network_controller
from tray import TrayIcon
from main_window import MainWindow


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
    IsWindowVisible = user32.IsWindowVisible
    SetForegroundWindow = user32.SetForegroundWindow
    ShowWindow = user32.ShowWindow

    SW_RESTORE = 9
    target_title = APP_NAME

    found = []

    def callback(hwnd, _lparam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buf, length + 1)
                if target_title in buf.value:
                    found.append(hwnd)
        return True

    GetWindowTextLengthW = user32.GetWindowTextLengthW
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
        self.tray.show()

        # 主界面（延迟创建）
        self.main_window = None

        # 更新托盘（含开机自启状态）
        self._update_tray()
        self.tray.update_startup_state(self._is_startup_enabled())

        # 开机恢复方案
        if self.config.get("restore_last_on_boot"):
            self._restore_last_profile()

        # 定时检查网络状态
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._check_network_status)
        self._status_timer.start(30000)

    def _update_tray(self):
        profiles = profile_manager.get_profiles(self.config)
        active_id = self.config.get("active_profile_id", "default")
        self.tray.update_profiles(profiles, active_id)

    def _check_network_status(self):
        active = profile_manager.get_active_profile(self.config)
        if not active:
            return

        adapter_ip = network_controller.get_default_adapter_ip()
        if adapter_ip:
            gateway = network_controller.get_gateway(adapter_ip)
            if gateway:
                if network_controller.ping(gateway):
                    self.tray.update_status("normal")
                else:
                    self.tray.update_status("warning")
            else:
                self.tray.update_status("normal")
        else:
            self.tray.update_status("warning")

    def _restore_last_profile(self):
        active = profile_manager.get_active_profile(self.config)
        if active and active["id"] != "default":
            success, _ = network_controller.apply_profile(active)
            if success:
                profile_manager.update_last_used(self.config, active["id"])

    def _on_tray_profile_selected(self, profile_id):
        profile = profile_manager.get_profile_by_id(self.config, profile_id)
        if profile:
            success, error = network_controller.apply_profile(profile)
            if success:
                profile_manager.set_active_profile(self.config, profile_id)
                profile_manager.update_last_used(self.config, profile_id)
                self._update_tray()
                self.tray.update_status("warning" if error else "normal")
            else:
                self.tray.update_status("error")

    def show_main_window(self):
        if not self.main_window:
            self.main_window = MainWindow(self.config)
            self.main_window.profile_applied.connect(self._on_profile_applied)
            self.main_window.profile_saved.connect(self._on_profile_saved)
            self.main_window.window_closed.connect(self._on_window_closed)

        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _on_profile_applied(self, profile_id):
        self._update_tray()
        self._check_network_status()

    def _on_profile_saved(self):
        self._update_tray()

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
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, self._get_exe_path())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

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
        self._set_start_with_windows(enabled)
        profile_manager.set_start_with_windows(self.config, enabled)
        self.tray.update_startup_state(enabled)

    def run(self):
        return self.app.exec()

    def quit(self):
        self.tray.hide()
        self.app.quit()


def main():
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
