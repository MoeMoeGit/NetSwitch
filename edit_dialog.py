"""编辑弹窗模块 - 方案新建/编辑/查看的独立弹窗"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QRadioButton, QPushButton, QGroupBox, QFormLayout,
    QButtonGroup, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import network_controller


class EditDialog(QDialog):
    """方案编辑弹窗"""

    def __init__(self, profile=None, parent=None):
        """
        profile: 要编辑的方案 dict，None 表示新建
        """
        super().__init__(parent)
        self.profile = profile
        self.is_locked = profile and profile.get("locked", False)
        self.saved = False

        self.setWindowTitle("方案详情" if self.is_locked else ("编辑方案" if profile else "新建方案"))
        self.setFixedWidth(360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 方案名称
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("输入方案名称")
        layout.addWidget(self._label("方案名称"))
        layout.addWidget(self.edit_name)

        # 备注
        self.edit_remark = QLineEdit()
        self.edit_remark.setPlaceholderText("备注（可选）")
        layout.addWidget(self._label("备注"))
        layout.addWidget(self.edit_remark)

        # 分割线
        layout.addWidget(self._separator())

        # IP 模式
        layout.addWidget(self._label("IP 模式"))
        ip_mode_layout = QHBoxLayout()
        self.radio_dhcp = QRadioButton("DHCP")
        self.radio_static = QRadioButton("手动")
        self.ip_mode_group = QButtonGroup()
        self.ip_mode_group.addButton(self.radio_dhcp)
        self.ip_mode_group.addButton(self.radio_static)
        self.radio_dhcp.toggled.connect(self._on_ip_mode_changed)
        ip_mode_layout.addWidget(self.radio_dhcp)
        ip_mode_layout.addWidget(self.radio_static)
        layout.addLayout(ip_mode_layout)

        # 手动 IP 字段容器
        self.ip_fields_widget = QFrame()
        ip_fields_layout = QVBoxLayout(self.ip_fields_widget)
        ip_fields_layout.setContentsMargins(0, 0, 0, 0)
        ip_fields_layout.setSpacing(6)

        self.edit_ip = QLineEdit()
        self.edit_ip.setPlaceholderText("192.168.1.100")
        self.edit_ip.textChanged.connect(self._validate)
        ip_fields_layout.addWidget(self._label("IP 地址"))
        ip_fields_layout.addWidget(self.edit_ip)

        self.combo_mask = QComboBox()
        self.combo_mask.addItems([
            "/24 - 255.255.255.0",
            "/16 - 255.255.0.0",
            "/8 - 255.0.0.0",
            "自定义",
        ])
        self.edit_mask_custom = QLineEdit()
        self.edit_mask_custom.setPlaceholderText("255.255.255.0")
        self.edit_mask_custom.setVisible(False)
        self.edit_mask_custom.textChanged.connect(self._validate)
        self.combo_mask.currentIndexChanged.connect(self._on_mask_changed)
        mask_layout = QVBoxLayout()
        mask_layout.setSpacing(2)
        mask_layout.addWidget(self.combo_mask)
        mask_layout.addWidget(self.edit_mask_custom)
        ip_fields_layout.addWidget(self._label("子网掩码"))
        ip_fields_layout.addLayout(mask_layout)

        self.edit_gateway = QLineEdit()
        self.edit_gateway.setPlaceholderText("192.168.1.1")
        self.edit_gateway.textChanged.connect(self._validate)
        ip_fields_layout.addWidget(self._label("默认网关"))
        ip_fields_layout.addWidget(self.edit_gateway)

        layout.addWidget(self.ip_fields_widget)

        # 分割线
        layout.addWidget(self._separator())

        # DNS 模式
        layout.addWidget(self._label("DNS 模式"))
        dns_mode_layout = QHBoxLayout()
        self.radio_dns_auto = QRadioButton("自动获取")
        self.radio_dns_manual = QRadioButton("手动指定")
        self.dns_mode_group = QButtonGroup()
        self.dns_mode_group.addButton(self.radio_dns_auto)
        self.dns_mode_group.addButton(self.radio_dns_manual)
        self.radio_dns_auto.toggled.connect(self._on_dns_mode_changed)
        dns_mode_layout.addWidget(self.radio_dns_auto)
        dns_mode_layout.addWidget(self.radio_dns_manual)
        layout.addLayout(dns_mode_layout)

        # 手动 DNS 字段容器
        self.dns_fields_widget = QFrame()
        dns_fields_layout = QVBoxLayout(self.dns_fields_widget)
        dns_fields_layout.setContentsMargins(0, 0, 0, 0)
        dns_fields_layout.setSpacing(6)

        self.edit_dns_primary = QLineEdit()
        self.edit_dns_primary.setPlaceholderText("8.8.8.8")
        self.edit_dns_primary.textChanged.connect(self._validate)
        dns_fields_layout.addWidget(self._label("首选 DNS"))
        dns_fields_layout.addWidget(self.edit_dns_primary)

        self.edit_dns_secondary = QLineEdit()
        self.edit_dns_secondary.setPlaceholderText("8.8.4.4（可选）")
        self.edit_dns_secondary.textChanged.connect(self._validate)
        dns_fields_layout.addWidget(self._label("备用 DNS"))
        dns_fields_layout.addWidget(self.edit_dns_secondary)

        layout.addWidget(self.dns_fields_widget)

        # 分割线
        layout.addWidget(self._separator())

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if self.is_locked:
            btn_close = QPushButton("关闭")
            btn_close.clicked.connect(self.close)
            btn_layout.addWidget(btn_close)
        else:
            self.btn_cancel = QPushButton("取消")
            self.btn_cancel.clicked.connect(self.close)
            btn_layout.addWidget(self.btn_cancel)

            self.btn_save = QPushButton("保存")
            self.btn_save.setStyleSheet(
                "QPushButton { background-color: #185FA5; color: white; padding: 6px 20px; }"
                "QPushButton:disabled { background-color: #ccc; color: #666; }"
            )
            self.btn_save.clicked.connect(self._on_save)
            btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

        # 填充数据
        if profile:
            self._load_profile(profile)
        else:
            self.radio_dhcp.setChecked(True)
            self.radio_dns_auto.setChecked(True)

        # 只读模式
        if self.is_locked:
            self._set_read_only()

        self._validate()

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; color: #333;")
        return lbl

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #ddd;")
        return line

    def _on_ip_mode_changed(self):
        is_static = self.radio_static.isChecked()
        self.ip_fields_widget.setVisible(is_static)
        self._validate()

    def _on_dns_mode_changed(self):
        is_manual = self.radio_dns_manual.isChecked()
        self.dns_fields_widget.setVisible(is_manual)
        self._validate()

    def _on_mask_changed(self, index):
        self.edit_mask_custom.setVisible(index == 3)
        self._validate()

    def _validate(self):
        if self.is_locked:
            return

        valid = True

        if not self.edit_name.text().strip():
            valid = False

        if self.radio_static.isChecked():
            if not network_controller.validate_ipv4(self.edit_ip.text()):
                self.edit_ip.setStyleSheet("border: 1px solid red;")
                valid = False
            else:
                self.edit_ip.setStyleSheet("")

            if self.combo_mask.currentIndex() == 3:
                if not network_controller.validate_ipv4(self.edit_mask_custom.text()):
                    self.edit_mask_custom.setStyleSheet("border: 1px solid red;")
                    valid = False
                else:
                    self.edit_mask_custom.setStyleSheet("")

            if not network_controller.validate_ipv4(self.edit_gateway.text()):
                self.edit_gateway.setStyleSheet("border: 1px solid red;")
                valid = False
            else:
                self.edit_gateway.setStyleSheet("")

        if self.radio_dns_manual.isChecked():
            if not network_controller.validate_ipv4(self.edit_dns_primary.text()):
                self.edit_dns_primary.setStyleSheet("border: 1px solid red;")
                valid = False
            else:
                self.edit_dns_primary.setStyleSheet("")

            if self.edit_dns_secondary.text().strip():
                if not network_controller.validate_ipv4(self.edit_dns_secondary.text()):
                    self.edit_dns_secondary.setStyleSheet("border: 1px solid red;")
                    valid = False
                else:
                    self.edit_dns_secondary.setStyleSheet("")
            else:
                self.edit_dns_secondary.setStyleSheet("")

        self.btn_save.setEnabled(valid)

    def _load_profile(self, profile):
        self.edit_name.setText(profile.get("name", ""))
        self.edit_remark.setText(profile.get("remark", ""))

        if profile.get("ip_mode") == "dhcp":
            self.radio_dhcp.setChecked(True)
        else:
            self.radio_static.setChecked(True)

        self.edit_ip.setText(profile.get("ip_address", ""))
        self.edit_gateway.setText(profile.get("gateway", ""))

        mask = profile.get("subnet_mask", "")
        if mask == "255.255.255.0":
            self.combo_mask.setCurrentIndex(0)
        elif mask == "255.255.0.0":
            self.combo_mask.setCurrentIndex(1)
        elif mask == "255.0.0.0":
            self.combo_mask.setCurrentIndex(2)
        else:
            self.combo_mask.setCurrentIndex(3)
            self.edit_mask_custom.setText(mask)

        if profile.get("dns_mode") == "auto":
            self.radio_dns_auto.setChecked(True)
        else:
            self.radio_dns_manual.setChecked(True)

        self.edit_dns_primary.setText(profile.get("dns_primary", ""))
        self.edit_dns_secondary.setText(profile.get("dns_secondary", ""))

    def _set_read_only(self):
        """所有字段只读"""
        self.edit_name.setReadOnly(True)
        self.edit_remark.setReadOnly(True)
        self.radio_dhcp.setEnabled(False)
        self.radio_static.setEnabled(False)
        self.edit_ip.setReadOnly(True)
        self.combo_mask.setEnabled(False)
        self.edit_mask_custom.setReadOnly(True)
        self.edit_gateway.setReadOnly(True)
        self.radio_dns_auto.setEnabled(False)
        self.radio_dns_manual.setEnabled(False)
        self.edit_dns_primary.setReadOnly(True)
        self.edit_dns_secondary.setReadOnly(True)

    def _on_save(self):
        if not self._validate_on_save():
            return
        self.saved = True
        self.accept()

    def _validate_on_save(self):
        """保存前最终校验"""
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, "提示", "请输入方案名称")
            return False

        if self.radio_static.isChecked():
            for field, name in [
                (self.edit_ip, "IP 地址"),
                (self.edit_gateway, "默认网关"),
            ]:
                if not network_controller.validate_ipv4(field.text()):
                    QMessageBox.warning(self, "提示", f"{name} 格式不正确")
                    return False

            if self.combo_mask.currentIndex() == 3:
                if not network_controller.validate_ipv4(self.edit_mask_custom.text()):
                    QMessageBox.warning(self, "提示", "子网掩码格式不正确")
                    return False

        if self.radio_dns_manual.isChecked():
            if not network_controller.validate_ipv4(self.edit_dns_primary.text()):
                QMessageBox.warning(self, "提示", "首选 DNS 格式不正确")
                return False
            if self.edit_dns_secondary.text().strip() and not network_controller.validate_ipv4(self.edit_dns_secondary.text()):
                QMessageBox.warning(self, "提示", "备用 DNS 格式不正确")
                return False

        return True

    def get_data(self):
        """获取表单数据"""
        data = {
            "name": self.edit_name.text().strip(),
            "remark": self.edit_remark.text().strip(),
            "ip_mode": "dhcp" if self.radio_dhcp.isChecked() else "static",
            "dns_mode": "auto" if self.radio_dns_auto.isChecked() else "manual",
        }

        if data["ip_mode"] == "static":
            data["ip_address"] = self.edit_ip.text()
            data["gateway"] = self.edit_gateway.text()
            if self.combo_mask.currentIndex() == 3:
                data["subnet_mask"] = self.edit_mask_custom.text()
            else:
                masks = ["255.255.255.0", "255.255.0.0", "255.0.0.0"]
                data["subnet_mask"] = masks[self.combo_mask.currentIndex()]

        if data["dns_mode"] == "manual":
            data["dns_primary"] = self.edit_dns_primary.text()
            data["dns_secondary"] = self.edit_dns_secondary.text()

        return data
