"""主界面模块 - 自定义无边框窗口、卡片列表、状态栏、操作按钮"""

from datetime import datetime
import traceback

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMenu, QLineEdit, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QThread
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QAction, QPen, QBrush,
    QGuiApplication,
)

import profile_manager
import network_controller
from edit_dialog import EditDialog


# ── 颜色常量 ──
COLOR_BG = "#FFFFFF"
COLOR_BG_SECONDARY = "#F5F5F5"
COLOR_BORDER = "#E0E0E0"
COLOR_TEXT = "#1A1A1A"
COLOR_TEXT_SECONDARY = "#888888"
COLOR_GREEN = "#16A34A"
COLOR_GREEN_BG = "#DCFCE7"
COLOR_GREEN_TEXT = "#15803D"
COLOR_BLUE_BG = "#E6F1FB"
COLOR_BLUE_BORDER = "#B5D4F4"
COLOR_BLUE_BTN = "#185FA5"
COLOR_RED_TEXT = "#A32D2D"
COLOR_RED_HOVER = "#C42B1C"


# ── 后台线程：执行方案切换 ──
class _ApplyWorker(QThread):
    finished = pyqtSignal(str, str)  # status, message

    def __init__(self, profile):
        super().__init__()
        self.profile = profile

    def run(self):
        status, error = network_controller.apply_profile(self.profile)
        self.finished.emit(status, error or "")


# ── 后台线程：删除激活方案前切换回 DHCP ──
class _DeleteWorker(QThread):
    finished = pyqtSignal(str, str)  # status, message

    def run(self):
        default_profile = profile_manager.get_default_profile()
        status, error = network_controller.apply_profile(default_profile)
        self.finished.emit(status, error or "")


# ── 卡片组件 ──
class ProfileCard(QWidget):
    """单个配置卡片"""

    clicked = pyqtSignal(str)        # profile_id
    double_clicked = pyqtSignal(str) # profile_id
    activate_requested = pyqtSignal(str)  # profile_id
    edit_requested = pyqtSignal(str)      # profile_id
    rename_requested = pyqtSignal(str, str)  # profile_id, new_name

    def __init__(self, profile, is_active=False, parent=None):
        super().__init__(parent)
        self.profile = profile
        self._is_active = is_active
        self._is_selected = False
        self._result_text = ""
        self._result_timer = QTimer(self)
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._clear_result)
        self._rename_edit = None

        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._update_style()

    @property
    def profile_id(self):
        return self.profile["id"]

    def set_active(self, active):
        self._is_active = active
        self._update_style()

    def set_selected(self, selected):
        self._is_selected = selected
        self._update_style()

    def show_result(self, success, message=""):
        if success:
            self._result_text = "✓ 成功"
        elif message:
            self._result_text = f"✗ {message}"
        else:
            self._result_text = "✗ 失败，已回滚"
        self._result_timer.start(2000)
        self._update_style()

    def _clear_result(self):
        self._result_text = ""
        self._update_style()

    def _update_style(self):
        self.update()

    def start_rename(self):
        if self.profile.get("locked"):
            return
        if self._rename_edit:
            return
        name = self.profile.get("name", "")
        self._rename_edit = QLineEdit(name, self)
        self._rename_edit.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Medium))
        self._rename_edit.setStyleSheet(
            "border: 1px solid #185FA5; border-radius: 3px; padding: 2px 4px; background: white;"
        )
        # 计算名称区域位置
        left = 16 + (8 if self._is_active else 0)
        self._rename_edit.setGeometry(left, 10, self.width() - left - 80, 24)
        self._rename_edit.show()
        self._rename_edit.setFocus()
        self._rename_edit.selectAll()
        self._rename_edit.editingFinished.connect(self._finish_rename)
        self._rename_edit.keyPressEvent = self._rename_key_press

    def _rename_key_press(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._finish_rename()
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel_rename()
        else:
            QLineEdit.keyPressEvent(self._rename_edit, event)

    def _finish_rename(self):
        if not self._rename_edit:
            return
        new_name = self._rename_edit.text().strip()
        self._rename_edit.deleteLater()
        self._rename_edit = None
        if new_name and new_name != self.profile.get("name"):
            self.rename_requested.emit(self.profile_id, new_name)

    def _cancel_rename(self):
        if self._rename_edit:
            self._rename_edit.deleteLater()
            self._rename_edit = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景和边框
        if self._is_selected and not self._is_active:
            bg = QColor(COLOR_BLUE_BG)
            border = QColor(COLOR_BLUE_BORDER)
        else:
            bg = QColor(COLOR_BG)
            border = QColor(COLOR_BORDER)

        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, w - 1, h - 1, 6, 6)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 0.5))
        painter.drawPath(path)

        # 激活中：左侧绿色竖线
        content_left = 16
        if self._is_active:
            bar = QPainterPath()
            bar.addRoundedRect(0, 0, 3, h, 1.5, 1.5)
            painter.fillPath(bar, QColor(COLOR_GREEN))
            content_left = 22

        # 名称
        if not self._rename_edit:
            name = self.profile.get("name", "")
            painter.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Medium))
            painter.setPen(QColor(COLOR_TEXT))
            painter.drawText(content_left, 10, w - content_left - 80, 24,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        # 副文本
        painter.setFont(QFont("Microsoft YaHei", 11))
        painter.setPen(QColor(COLOR_TEXT_SECONDARY))
        if self._result_text:
            sub = self._result_text
            painter.setPen(QColor(COLOR_GREEN if "✓" in self._result_text else COLOR_RED_TEXT))
        elif self._is_active:
            if self.profile.get("ip_mode") == "dhcp":
                sub = "自动获取"
            else:
                sub = self.profile.get("ip_address", "")
        else:
            ip = self.profile.get("ip_address", "")
            last = self.profile.get("last_used")
            if ip and last:
                sub = f"{ip} · {self._format_time_ago(last)}"
            elif ip:
                sub = ip
            elif last:
                sub = self._format_time_ago(last)
            elif self.profile.get("ip_mode") == "dhcp":
                sub = "自动获取 IP"
            else:
                sub = ""
        painter.drawText(content_left, 36, w - content_left - 80, 18,
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)

        # 激活中标签
        if self._is_active and not self._result_text:
            tag_text = "激活中"
            tag_font = QFont("Microsoft YaHei", 10)
            painter.setFont(tag_font)
            tag_w = painter.fontMetrics().horizontalAdvance(tag_text) + 14
            tag_h = 20
            tag_x = w - tag_w - 12
            tag_y = (h - tag_h) // 2
            tag_path = QPainterPath()
            tag_path.addRoundedRect(tag_x, tag_y, tag_w, tag_h, 10, 10)
            painter.fillPath(tag_path, QColor(COLOR_GREEN_BG))
            painter.setPen(QColor(COLOR_GREEN_TEXT))
            painter.drawText(tag_x, tag_y, tag_w, tag_h,
                             Qt.AlignmentFlag.AlignCenter, tag_text)

        painter.end()

    def _format_time_ago(self, iso_str):
        try:
            dt = datetime.fromisoformat(iso_str)
            delta = datetime.now() - dt
            if delta.days > 0:
                return f"{delta.days}天前"
            hours = delta.seconds // 3600
            if hours > 0:
                return f"{hours}小时前"
            minutes = delta.seconds // 60
            if minutes > 0:
                return f"{minutes}分钟前"
            return "刚刚"
        except Exception:
            return ""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.profile_id)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.profile_id)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { min-width: 120px; }"
            "QMenu::item { padding: 6px 24px 6px 12px; }"
        )
        is_locked = self.profile.get("locked", False)

        act_activate = menu.addAction("激活")
        act_activate.triggered.connect(lambda: self.activate_requested.emit(self.profile_id))

        act_edit = menu.addAction("编辑")
        act_edit.triggered.connect(lambda: self.edit_requested.emit(self.profile_id))

        act_rename = menu.addAction("重命名")
        act_rename.setEnabled(not is_locked)
        act_rename.triggered.connect(self.start_rename)

        menu.addSeparator()

        act_delete = menu.addAction("删除")
        act_delete.setEnabled(not is_locked)
        if not is_locked:
            act_delete.setForeground(QColor(COLOR_RED_TEXT))
        act_delete.triggered.connect(self._on_delete)

        menu.exec(event.globalPos())

    def _on_delete(self):
        # 通过信号传递给主窗口处理
        parent = self.parent()
        while parent and not isinstance(parent, MainWindow):
            parent = parent.parent()
        if parent:
            parent._delete_profile(self.profile_id)


# ── 主窗口 ──
class MainWindow(QWidget):
    """自定义无边框主窗口"""

    profile_applied = pyqtSignal(str)
    profile_saved = pyqtSignal()
    window_closed = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._drag_pos = None
        self._selected_id = None
        self._apply_worker = None
        self._delete_worker = None
        self._pending_delete_id = None
        self._apply_in_progress = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setWindowTitle("NetSwitch")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedWidth(340)
        self.setMinimumHeight(300)

        self._build_ui()
        self._load_cards()
        self._restore_position()

        self._network_snapshot = {
            "status": "warning",
            "ip": None,
            "gateway": None,
        }

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 外层容器（圆角 + 边框）
        self._container = QWidget()
        self._container.setObjectName("mainContainer")
        self._container.setStyleSheet(
            "#mainContainer { background: white; border: 1px solid #ddd; border-radius: 8px; }"
        )
        root.addWidget(self._container)

        vbox = QVBoxLayout(self._container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── 标题栏 ──
        title_bar = QWidget()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet(f"background: {COLOR_BG_SECONDARY}; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(12, 0, 0, 0)

        title_label = QLabel("NetSwitch")
        title_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Medium))
        title_label.setStyleSheet(f"color: {COLOR_TEXT};")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()

        btn_min = QPushButton("─")
        btn_min.setFixedSize(46, 36)
        btn_min.setStyleSheet(
            "QPushButton { border: none; font-size: 14px; }"
            "QPushButton:hover { background: #e0e0e0; }"
        )
        btn_min.clicked.connect(self.showMinimized)
        tb_layout.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(46, 36)
        btn_close.setStyleSheet(
            "QPushButton { border: none; font-size: 14px; }"
            f"QPushButton:hover {{ background: {COLOR_RED_HOVER}; color: white; }}"
        )
        btn_close.clicked.connect(self._on_close)
        tb_layout.addWidget(btn_close)

        vbox.addWidget(title_bar)
        vbox.addWidget(self._make_separator())

        # ── 状态栏 ──
        status_bar = QWidget()
        status_bar.setFixedHeight(32)
        status_bar.setStyleSheet(f"background: {COLOR_BG_SECONDARY};")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)

        self._status_dot = QLabel("●")
        self._status_dot.setFixedWidth(10)
        self._status_dot.setStyleSheet(f"color: {COLOR_GREEN}; font-size: 8px;")
        sb_layout.addWidget(self._status_dot)

        self._status_label = QLabel("当前 —  检测中…")
        self._status_label.setFont(QFont("Microsoft YaHei", 12))
        self._status_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY};")
        sb_layout.addWidget(self._status_label)
        sb_layout.addStretch()

        vbox.addWidget(status_bar)
        vbox.addWidget(self._make_separator())

        # ── 卡片列表（可滚动） ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")

        self._card_container = QWidget()
        self._card_container.setStyleSheet("background: white;")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(10, 10, 10, 6)
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()

        self._scroll.setWidget(self._card_container)
        vbox.addWidget(self._scroll)

        # ── 底部操作栏 ──
        vbox.addWidget(self._make_separator())

        bottom = QWidget()
        bottom.setFixedHeight(44)
        bot_layout = QHBoxLayout(bottom)
        bot_layout.setContentsMargins(10, 0, 10, 0)

        self.btn_new = QPushButton("新建")
        self.btn_new.setStyleSheet(
            f"QPushButton {{ border: 1px solid {COLOR_BORDER}; border-radius: 4px; "
            f"padding: 6px 14px; font-size: 12px; color: {COLOR_TEXT}; "
            f"background: {COLOR_BG_SECONDARY}; }}"
            "QPushButton:hover { background: #ededed; }"
        )
        self.btn_new.clicked.connect(self._on_new)
        bot_layout.addWidget(self.btn_new)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setStyleSheet(
            f"QPushButton {{ border: 1px solid #e8d5d5; border-radius: 4px; "
            f"padding: 6px 14px; font-size: 12px; color: {COLOR_RED_TEXT}; "
            "background: #FFF5F5; }"
            "QPushButton:hover { background: #FDE8E8; }"
            "QPushButton:disabled { color: #B8B8B8; border-color: #EEE; background: #FAFAFA; }"
        )
        self.btn_delete.clicked.connect(self._on_delete_click)
        self.btn_delete.setEnabled(False)
        bot_layout.addWidget(self.btn_delete)

        bot_layout.addStretch()

        self.btn_activate = QPushButton("激活")
        self.btn_activate.setStyleSheet(
            f"QPushButton {{ background: {COLOR_BLUE_BTN}; color: white; font-weight: 500; "
            f"padding: 6px 20px; border-radius: 4px; font-size: 12px; }}"
            "QPushButton:hover { background: #1a6fa0; }"
            "QPushButton:disabled { background: #ccc; color: #666; }"
        )
        self.btn_activate.clicked.connect(self._on_activate)
        self.btn_activate.setEnabled(False)
        bot_layout.addWidget(self.btn_activate)

        vbox.addWidget(bottom)

    def _make_separator(self):
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {COLOR_BORDER};")
        return line

    def _load_cards(self):
        """加载/刷新卡片列表"""
        # 清除旧卡片
        while self._card_layout.count() > 1:  # 保留 stretch
            item = self._card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        profiles = profile_manager.get_profiles(self.config)
        active_id = self.config.get("active_profile_id", "default")

        for profile in profiles:
            card = ProfileCard(profile, is_active=(profile["id"] == active_id))
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.activate_requested.connect(self._on_card_activate_requested)
            card.edit_requested.connect(self._on_card_edit_requested)
            card.rename_requested.connect(self._on_rename)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

        # 自动选中激活中的卡片
        self._selected_id = active_id
        self._update_selection()
        self._update_buttons()

    def _on_card_clicked(self, profile_id):
        self._selected_id = profile_id
        self._update_selection()
        self._update_buttons()

    def _on_card_double_clicked(self, profile_id):
        self._selected_id = profile_id
        self._update_selection()
        self._update_buttons()
        active_id = self.config.get("active_profile_id", "default")
        if profile_id != active_id:
            self._on_activate()

    def _on_card_activate_requested(self, profile_id):
        self._selected_id = profile_id
        self._update_selection()
        self._update_buttons()
        active_id = self.config.get("active_profile_id", "default")
        if profile_id != active_id:
            self._on_activate()

    def _on_card_edit_requested(self, profile_id):
        profile = profile_manager.get_profile_by_id(self.config, profile_id)
        if profile:
            self._open_edit_dialog(profile)

    def _update_selection(self):
        for i in range(self._card_layout.count()):
            item = self._card_layout.itemAt(i)
            card = item.widget()
            if isinstance(card, ProfileCard):
                card.set_selected(
                    card.profile_id == self._selected_id
                    and card.profile_id != self.config.get("active_profile_id")
                )

    def _update_buttons(self):
        active_id = self.config.get("active_profile_id", "default")
        is_active = self._selected_id == active_id
        is_locked = False

        if self._selected_id:
            profile = profile_manager.get_profile_by_id(self.config, self._selected_id)
            is_locked = profile and profile.get("locked", False)

        self.btn_activate.setEnabled(self._selected_id is not None and not is_active)
        self.btn_delete.setEnabled(self._selected_id is not None and not is_locked)

    def _on_new(self):
        self._open_edit_dialog(None)

    def _on_delete_click(self):
        if self._selected_id:
            self._delete_profile(self._selected_id)

    def _delete_profile(self, profile_id):
        profile = profile_manager.get_profile_by_id(self.config, profile_id)
        if not profile or profile.get("locked"):
            return

        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认删除",
            f"确认删除「{profile['name']}」？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        is_active = self.config.get("active_profile_id") == profile_id
        if is_active and profile_id != "default":
            # 删除激活方案需先切回 DHCP，使用后台线程避免阻塞 UI
            self._pending_delete_id = profile_id
            self.btn_delete.setEnabled(False)
            self.btn_activate.setEnabled(False)
            self.btn_delete.setText("删除中…")

            self._delete_worker = _DeleteWorker()
            self._delete_worker.finished.connect(self._on_delete_dhcp_finished)
            self._delete_worker.start()
        else:
            self._do_delete_profile(profile_id)

    def _on_delete_dhcp_finished(self, status, message):
        self.btn_delete.setText("删除")
        profile_id = self._pending_delete_id
        self._pending_delete_id = None
        self._delete_worker = None

        if status == network_controller.FAILED:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "无法删除", f"切换回 DHCP 失败：{message}\n方案未删除。")
            self._update_buttons()
            return

        self._do_delete_profile(profile_id)

    def _do_delete_profile(self, profile_id):
        config = self.config
        config["profiles"] = [p for p in config["profiles"] if p["id"] != profile_id]
        if config.get("active_profile_id") == profile_id:
            config["active_profile_id"] = "default"
        profile_manager.save_config(config)

        if self._selected_id == profile_id:
            self._selected_id = None
        self._load_cards()
        self.profile_saved.emit()

    def _on_activate(self):
        if not self._selected_id:
            return
        if self._apply_worker and self._apply_worker.isRunning():
            return
        if network_controller._APPLY_LOCK.locked():
            return

        profile = profile_manager.get_profile_by_id(self.config, self._selected_id)
        if not profile:
            return

        # 按钮变为 loading 状态
        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("切换中…")
        self._apply_in_progress = True

        self._apply_worker = _ApplyWorker(profile)
        self._apply_worker.finished.connect(
            lambda status, msg: self._on_apply_finished(profile, status, msg)
        )
        self._apply_worker.start()

    def _on_apply_finished(self, profile, status, message):
        try:
            self._apply_in_progress = False
            self.btn_activate.setText("激活")
            self._update_buttons()

            if status == network_controller.FAILED:
                for i in range(self._card_layout.count()):
                    item = self._card_layout.itemAt(i)
                    card = item.widget()
                    if isinstance(card, ProfileCard) and card.profile_id == profile["id"]:
                        card.show_result(False, message)
                        break
            else:
                profile_manager.set_active_profile(self.config, profile["id"])
                profile_manager.update_last_used(self.config, profile["id"])
                self.profile_applied.emit(profile["id"])
                self._load_cards()
        except Exception as e:
            try:
                network_controller._log_error(f"apply finish exception: {e}")
                import traceback
                network_controller._log_error(traceback.format_exc().rstrip())
            except Exception:
                pass
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "NetSwitch", f"切换已完成但界面处理失败：{e}")
        finally:
            self._apply_worker = None

    def is_applying(self):
        return self._apply_in_progress

    def _open_edit_dialog(self, profile):
        dlg = EditDialog(profile, parent=self)
        if dlg.exec() == EditDialog.DialogCode.Accepted and dlg.saved:
            data = dlg.get_data()
            if profile:
                profile_manager.update_profile(self.config, profile["id"], **data)
            else:
                profile_manager.create_profile(self.config, **data)
            self._load_cards()
            self.profile_saved.emit()

    def _on_rename(self, profile_id, new_name):
        profile_manager.update_profile(self.config, profile_id, name=new_name)
        self._load_cards()
        self.profile_saved.emit()

    def update_network_snapshot(self, snapshot):
        """由主程序推送当前网络状态快照。"""
        self._network_snapshot = snapshot or {}
        status = self._network_snapshot.get("status", "warning")
        ip = self._network_snapshot.get("ip")
        gateway = self._network_snapshot.get("gateway")

        if ip:
            self._status_label.setText(f"当前 —  {ip}   网关 {gateway or '—'}")
        else:
            self._status_label.setText("当前 —  未检测到网络")

        self.set_network_status(status)

    def set_network_status(self, status):
        """由主程序调用，同步网络状态到状态栏 dot 颜色"""
        color_map = {
            "normal": COLOR_GREEN,
            "warning": "#D97706",
            "error": "#F44336",
            "switching": COLOR_GREEN,
        }
        color = color_map.get(status, COLOR_GREEN)
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 8px;")

    def _on_close(self):
        self._save_position()
        self.hide()
        self.window_closed.emit()

    def closeEvent(self, event):
        event.ignore()
        self._on_close()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_cards()
        self.update_network_snapshot(self._network_snapshot)

    # ── 窗口拖动 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 只在标题栏区域拖动
            if event.position().y() < 36:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── 窗口位置记忆 ──

    def _restore_position(self):
        x, y = profile_manager.get_window_position(self.config)
        if x is None or y is None:
            return

        # 校验坐标在当前任意屏幕范围内
        for screen in QGuiApplication.screens():
            geo = screen.availableGeometry()
            if geo.contains(x, y):
                self.move(x, y)
                return

    def _save_position(self):
        pos = self.pos()
        profile_manager.save_window_position(self.config, pos.x(), pos.y())

    # ── 键盘快捷键 ──

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self._selected_id is not None:
                active_id = self.config.get("active_profile_id", "default")
                if self._selected_id != active_id:
                    self._on_activate()

        elif event.key() == Qt.Key.Key_Delete:
            if self._selected_id is not None:
                profile = profile_manager.get_profile_by_id(self.config, self._selected_id)
                if profile and not profile.get("locked"):
                    self._on_delete_click()

        elif event.key() == Qt.Key.Key_Escape:
            if self._selected_id is not None:
                self._selected_id = None
                self._update_selection()
                self._update_buttons()
            else:
                self._on_close()

        elif event.key() == Qt.Key.Key_F2:
            if self._selected_id is not None:
                profile = profile_manager.get_profile_by_id(self.config, self._selected_id)
                if profile and not profile.get("locked"):
                    for i in range(self._card_layout.count()):
                        item = self._card_layout.itemAt(i)
                        card = item.widget()
                        if isinstance(card, ProfileCard) and card.profile_id == self._selected_id:
                            card.start_rename()
                            break

        else:
            super().keyPressEvent(event)
