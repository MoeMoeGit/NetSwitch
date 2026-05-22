"""设置弹窗模块 - 开机自启、开机恢复上次方案"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
)
from PyQt6.QtCore import pyqtSignal, Qt

import profile_manager


class SettingsDialog(QDialog):
    """极简设置弹窗"""

    startup_toggled = pyqtSignal(bool)  # 开机自启开关

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("设置")
        self.setFixedSize(260, 130)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 12)

        self.chk_startup = QCheckBox("开机自启")
        self.chk_startup.setChecked(
            profile_manager.get_start_with_windows(self.config)
        )
        self.chk_startup.toggled.connect(self._on_startup_toggled)
        layout.addWidget(self.chk_startup)

        self.chk_restore = QCheckBox("开机恢复上次方案")
        self.chk_restore.setChecked(
            profile_manager.get_restore_last_on_boot(self.config)
        )
        self.chk_restore.toggled.connect(self._on_restore_toggled)
        layout.addWidget(self.chk_restore)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _on_startup_toggled(self, checked):
        profile_manager.set_start_with_windows(self.config, checked)
        self.startup_toggled.emit(checked)

    def _on_restore_toggled(self, checked):
        profile_manager.set_restore_last_on_boot(self.config, checked)
