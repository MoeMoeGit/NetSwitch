"""设置弹窗模块 - 常规、更新、帮助与反馈"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLabel,
    QGroupBox, QFormLayout, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt

import profile_manager


class SettingsDialog(QDialog):
    """极简设置弹窗"""

    startup_toggled = pyqtSignal(bool)  # 开机自启开关
    check_update_requested = pyqtSignal()
    open_homepage_requested = pyqtSignal()
    open_issues_requested = pyqtSignal()

    def __init__(self, config, version="", parent=None):
        super().__init__(parent)
        self.config = config
        self.version = version or "0.0.0"

        self.setWindowTitle("设置")
        self.setFixedSize(340, 340)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 12)

        general_box = QGroupBox("常规")
        general_layout = QVBoxLayout(general_box)
        general_layout.setSpacing(8)
        self.chk_startup = QCheckBox("开机自启")
        self.chk_startup.setChecked(
            profile_manager.get_start_with_windows(self.config)
        )
        self.chk_startup.toggled.connect(self._on_startup_toggled)
        general_layout.addWidget(self.chk_startup)
        self.chk_restore = QCheckBox("开机恢复上次方案")
        self.chk_restore.setChecked(
            profile_manager.get_restore_last_on_boot(self.config)
        )
        self.chk_restore.toggled.connect(self._on_restore_toggled)
        general_layout.addWidget(self.chk_restore)
        layout.addWidget(general_box)

        update_box = QGroupBox("更新")
        update_layout = QFormLayout(update_box)
        update_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        update_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        update_layout.setHorizontalSpacing(10)
        update_layout.setVerticalSpacing(8)

        self.lbl_version = QLabel(self.version)
        self.lbl_version.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        update_layout.addRow("当前版本", self.lbl_version)

        self.btn_check_update = QPushButton("检查更新")
        self.btn_check_update.clicked.connect(self.check_update_requested.emit)
        update_layout.addRow("", self.btn_check_update)
        layout.addWidget(update_box)

        help_box = QGroupBox("帮助与反馈")
        help_layout = QVBoxLayout(help_box)
        help_layout.setSpacing(8)

        self.lbl_author = QLabel("作者：Lucas Liu")
        self.lbl_author.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        help_layout.addWidget(self.lbl_author)

        self.lbl_email = QLabel("邮箱：lucas6.zju@vip.163.com")
        self.lbl_email.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        help_layout.addWidget(self.lbl_email)

        link_row = QHBoxLayout()
        self.btn_homepage = QPushButton("GitHub 主页")
        self.btn_homepage.clicked.connect(self.open_homepage_requested.emit)
        link_row.addWidget(self.btn_homepage)

        self.btn_issues = QPushButton("Issue 反馈")
        self.btn_issues.clicked.connect(self.open_issues_requested.emit)
        link_row.addWidget(self.btn_issues)
        help_layout.addLayout(link_row)
        layout.addWidget(help_box)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _on_startup_toggled(self, checked):
        self.startup_toggled.emit(checked)

    def _on_restore_toggled(self, checked):
        profile_manager.set_restore_last_on_boot(self.config, checked)
