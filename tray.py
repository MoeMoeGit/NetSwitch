"""托盘图标模块 - 系统托盘图标、右键菜单、状态更新"""

import os
import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal

# 图标背景色映射
_ICON_COLORS = {
    "normal":    QColor(0x0E, 0x74, 0x90),   # 深青色
    "warning":   QColor(0xD9, 0x77, 0x06),   # 橙黄色
    "error":     QColor(0xDC, 0x26, 0x26),   # 红色
    "switching": QColor(0x0E, 0x74, 0x90),   # 切换中同正常色
}

ICON_SIZE = 32


def _make_icon_pixmap(color):
    """用纯色背景 + 白色 N 字生成托盘图标"""
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(color)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Arial", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    painter.end()
    return pixmap


# PyInstaller 打包后资源在临时目录根，开发环境在 assets/ 目录
if getattr(sys, 'frozen', False):
    _DIR = sys._MEIPASS
else:
    _DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

ICON_PATH = os.path.join(_DIR, "icon.ico")
TRAY_16 = os.path.join(_DIR, "tray_16.png")
TRAY_32 = os.path.join(_DIR, "tray_32.png")


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标"""

    profile_selected = pyqtSignal(str)
    open_main_window = pyqtSignal()
    quit_app = pyqtSignal()
    toggle_startup = pyqtSignal(bool)  # 开机自启开关
    open_settings = pyqtSignal()       # 打开设置弹窗

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profiles = []
        self.active_profile_id = "default"
        self.status = "normal"
        self._startup_enabled = False

        self.update_icon(self.status)
        self._build_menu()
        self.activated.connect(self._on_activated)

    def update_icon(self, status):
        """根据状态动态生成并设置托盘图标"""
        color = _ICON_COLORS.get(status, _ICON_COLORS["normal"])
        pixmap = _make_icon_pixmap(color)
        self.setIcon(QIcon(pixmap))

    def update_status(self, status):
        self.status = status
        self.update_icon(status)
        self._update_tooltip()

    def _build_menu(self):
        self.menu = QMenu()
        self.setContextMenu(self.menu)

    def update_profiles(self, profiles, active_profile_id):
        self.profiles = profiles
        self.active_profile_id = active_profile_id
        self._rebuild_menu()
        self._update_tooltip()

    def _update_tooltip(self):
        active_name = "未选择方案"
        for p in self.profiles:
            if p["id"] == self.active_profile_id:
                active_name = p["name"]
                break
        status_map = {"normal": "正常", "warning": "网关不通", "error": "切换失败", "switching": "切换中…"}
        status_text = status_map.get(self.status, "")
        tip = f"NetSwitch - {active_name}"
        if status_text:
            tip += f" ({status_text})"
        self.setToolTip(tip)

    def update_startup_state(self, enabled):
        """更新开机自启状态（由主程序调用）"""
        self._startup_enabled = enabled

    def _rebuild_menu(self):
        self.menu.clear()

        for profile in self.profiles:
            action = QAction(profile["name"], self.menu)
            action.setData(profile["id"])
            if profile["id"] == self.active_profile_id:
                action.setCheckable(True)
                action.setChecked(True)
            action.triggered.connect(
                lambda checked, pid=profile["id"]: self.profile_selected.emit(pid)
            )
            self.menu.addAction(action)

        self.menu.addSeparator()

        open_action = QAction("打开主界面", self.menu)
        open_action.triggered.connect(self.open_main_window.emit)
        self.menu.addAction(open_action)

        startup_action = QAction("开机自启", self.menu)
        startup_action.setCheckable(True)
        startup_action.setChecked(self._startup_enabled)
        startup_action.triggered.connect(
            lambda checked: self.toggle_startup.emit(checked)
        )
        self.menu.addAction(startup_action)

        settings_action = QAction("设置", self.menu)
        settings_action.triggered.connect(self.open_settings.emit)
        self.menu.addAction(settings_action)

        self.menu.addSeparator()

        quit_action = QAction("退出", self.menu)
        quit_action.triggered.connect(self.quit_app.emit)
        self.menu.addAction(quit_action)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_main_window.emit()
