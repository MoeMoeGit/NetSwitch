"""托盘图标模块 - 系统托盘图标、右键菜单、状态更新"""

import os
import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal


# PyInstaller 打包后资源在临时目录，开发环境在脚本目录
if getattr(sys, 'frozen', False):
    _DIR = sys._MEIPASS
else:
    _DIR = os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(_DIR, "icon.ico")
TRAY_16 = os.path.join(_DIR, "tray_16.png")
TRAY_32 = os.path.join(_DIR, "tray_32.png")


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标"""

    profile_selected = pyqtSignal(str)
    open_main_window = pyqtSignal()
    quit_app = pyqtSignal()
    toggle_startup = pyqtSignal(bool)  # 开机自启开关

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profiles = []
        self.active_profile_id = "default"
        self.status = "normal"  # normal / warning / error
        self._startup_enabled = False

        self._load_icon()
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _load_icon(self):
        """加载图标文件"""
        if os.path.exists(ICON_PATH):
            self._icon = QIcon(ICON_PATH)
        elif os.path.exists(TRAY_32):
            self._icon = QIcon(TRAY_32)
        else:
            self._icon = self._generate_fallback()
        self.setIcon(self._icon)

    def _generate_fallback(self):
        """无图标文件时的备用方案"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0x0E, 0x74, 0x90))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Arial", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
        painter.end()
        return QIcon(pixmap)

    def _build_menu(self):
        self.menu = QMenu()
        self.setContextMenu(self.menu)

    def update_profiles(self, profiles, active_profile_id):
        self.profiles = profiles
        self.active_profile_id = active_profile_id
        self._rebuild_menu()
        self._update_tooltip()

    def update_status(self, status):
        self.status = status
        # 图标文件不变，通过 tooltip 体现状态
        self._update_tooltip()

    def _update_tooltip(self):
        active_name = "未选择方案"
        for p in self.profiles:
            if p["id"] == self.active_profile_id:
                active_name = p["name"]
                break
        status_map = {"normal": "正常", "warning": "网关不通", "error": "切换失败"}
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
            action = QAction(profile["name"], self)
            action.setData(profile["id"])
            if profile["id"] == self.active_profile_id:
                action.setCheckable(True)
                action.setChecked(True)
            action.triggered.connect(
                lambda checked, pid=profile["id"]: self.profile_selected.emit(pid)
            )
            self.menu.addAction(action)

        self.menu.addSeparator()

        open_action = QAction("打开主界面", self)
        open_action.triggered.connect(self.open_main_window.emit)
        self.menu.addAction(open_action)

        startup_action = QAction("开机自启", self)
        startup_action.setCheckable(True)
        startup_action.setChecked(self._startup_enabled)
        startup_action.triggered.connect(
            lambda checked: self.toggle_startup.emit(checked)
        )
        self.menu.addAction(startup_action)

        self.menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app.emit)
        self.menu.addAction(quit_action)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_main_window.emit()
