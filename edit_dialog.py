"""编辑弹窗模块 - 方案新建/编辑/查看的独立弹窗"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QRadioButton, QPushButton, QGroupBox, QFormLayout,
    QButtonGroup, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import network_controller
import ui_style


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

        title = "方案详情" if self.is_locked else ("编辑方案" if profile else "新建方案")
        self.setWindowTitle(title)
        self.setFixedWidth(420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        ui_style.apply_common_style(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QLabel(title)
        header.setFont(QFont("Microsoft YaHei UI", 17, QFont.Weight.DemiBold))
        layout.addWidget(header)

        subtitle = QLabel("配置当前优先网卡的 IP、网关和 DNS。")
        subtitle.setProperty("muted", True)
        layout.addWidget(subtitle)

        # 基础信息
        profile_box = QGroupBox("基础信息")
        profile_form = self._make_form(profile_box)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("例如：公司网络 / 家庭软路由")
        self.edit_name.textChanged.connect(self._validate)
        profile_form.addRow("方案名称", self.edit_name)

        self.edit_remark = QLineEdit()
        self.edit_remark.setPlaceholderText("备注，可选")
        profile_form.addRow("备注", self.edit_remark)
        layout.addWidget(profile_box)

        # IP 配置
        ip_box = QGroupBox("IP 配置")
        ip_layout = QVBoxLayout(ip_box)
        ip_layout.setContentsMargins(12, 16, 12, 12)
        ip_layout.setSpacing(10)

        ip_mode_layout = QHBoxLayout()
        ip_mode_layout.setSpacing(18)
        self.radio_dhcp = QRadioButton("DHCP 自动获取")
        self.radio_static = QRadioButton("手动指定")
        self.ip_mode_group = QButtonGroup()
        self.ip_mode_group.addButton(self.radio_dhcp)
        self.ip_mode_group.addButton(self.radio_static)
        self.radio_dhcp.toggled.connect(self._on_ip_mode_changed)
        ip_mode_layout.addWidget(self.radio_dhcp)
        ip_mode_layout.addWidget(self.radio_static)
        ip_mode_layout.addStretch()
        ip_layout.addLayout(ip_mode_layout)

        self.ip_fields_widget = QFrame()
        ip_form = self._make_form(self.ip_fields_widget)

        self.edit_ip = QLineEdit()
        self.edit_ip.setPlaceholderText("192.168.1.100")
        self.edit_ip.textChanged.connect(self._validate)
        ip_form.addRow("IP 地址", self.edit_ip)

        self.combo_mask = QComboBox()
        self.combo_mask.addItems([
            "/24 - 255.255.255.0",
            "/16 - 255.255.0.0",
            "/8 - 255.0.0.0",
            "自定义",
        ])
        self.combo_mask.currentIndexChanged.connect(self._on_mask_changed)
        ip_form.addRow("子网掩码", self.combo_mask)

        self.edit_mask_custom = QLineEdit()
        self.edit_mask_custom.setPlaceholderText("255.255.255.0")
        self.edit_mask_custom.setVisible(False)
        self.edit_mask_custom.textChanged.connect(self._validate)
        ip_form.addRow("", self.edit_mask_custom)

        self.edit_gateway = QLineEdit()
        self.edit_gateway.setPlaceholderText("192.168.1.1")
        self.edit_gateway.textChanged.connect(self._validate)
        ip_form.addRow("默认网关", self.edit_gateway)

        ip_layout.addWidget(self.ip_fields_widget)
        layout.addWidget(ip_box)

        # DNS 配置
        dns_box = QGroupBox("DNS 配置")
        dns_layout = QVBoxLayout(dns_box)
        dns_layout.setContentsMargins(12, 16, 12, 12)
        dns_layout.setSpacing(10)

        dns_mode_layout = QHBoxLayout()
        dns_mode_layout.setSpacing(18)
        self.radio_dns_auto = QRadioButton("自动获取")
        self.radio_dns_manual = QRadioButton("手动指定")
        self.dns_mode_group = QButtonGroup()
        self.dns_mode_group.addButton(self.radio_dns_auto)
        self.dns_mode_group.addButton(self.radio_dns_manual)
        self.radio_dns_auto.toggled.connect(self._on_dns_mode_changed)
        dns_mode_layout.addWidget(self.radio_dns_auto)
        dns_mode_layout.addWidget(self.radio_dns_manual)
        dns_mode_layout.addStretch()
        dns_layout.addLayout(dns_mode_layout)

        self.dns_fields_widget = QFrame()
        dns_form = self._make_form(self.dns_fields_widget)

        self.edit_dns_primary = QLineEdit()
        self.edit_dns_primary.setPlaceholderText("8.8.8.8")
        self.edit_dns_primary.textChanged.connect(self._validate)
        dns_form.addRow("首选 DNS", self.edit_dns_primary)

        self.edit_dns_secondary = QLineEdit()
        self.edit_dns_secondary.setPlaceholderText("8.8.4.4，可选")
        self.edit_dns_secondary.textChanged.connect(self._validate)
        dns_form.addRow("备用 DNS", self.edit_dns_secondary)

        dns_layout.addWidget(self.dns_fields_widget)
        layout.addWidget(dns_box)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 2, 0, 0)
        btn_layout.addStretch()

        if self.is_locked:
            btn_close = QPushButton("关闭")
            btn_close.setObjectName("primaryButton")
            btn_close.clicked.connect(self.close)
            btn_layout.addWidget(btn_close)
        else:
            self.btn_cancel = QPushButton("取消")
            self.btn_cancel.setObjectName("textButton")
            self.btn_cancel.clicked.connect(self.close)
            btn_layout.addWidget(self.btn_cancel)

            self.btn_save = QPushButton("保存")
            self.btn_save.setObjectName("primaryButton")
            self.btn_save.clicked.connect(self._on_save)
            btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

        if profile:
            self._load_profile(profile)
        else:
            self.radio_dhcp.setChecked(True)
            self.radio_dns_auto.setChecked(True)

        if self.is_locked:
            self._set_read_only()

        self._validate()
        self.adjustSize()

    def _make_form(self, parent):
        form = QFormLayout(parent)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        return form

    def _grow_to_fit(self):
        """切换字段显示后只增高、不收缩；避免反复切换造成弹窗上下抖动。"""
        hint = self.sizeHint()
        if hint.height() > self.height():
            self.resize(self.width(), hint.height())

    def _set_invalid(self, widget, invalid):
        widget.setProperty("invalid", invalid)
        ui_style.polish(widget)

    def _on_ip_mode_changed(self):
        is_static = self.radio_static.isChecked()
        self.ip_fields_widget.setVisible(is_static)
        self._grow_to_fit()
        self._validate()

    def _on_dns_mode_changed(self):
        is_manual = self.radio_dns_manual.isChecked()
        self.dns_fields_widget.setVisible(is_manual)
        self._grow_to_fit()
        self._validate()

    def _on_mask_changed(self, index):
        self.edit_mask_custom.setVisible(index == 3)
        self._grow_to_fit()
        self._validate()

    def _validate(self):
        if self.is_locked:
            return

        valid = True

        name_text = self.edit_name.text()
        name_missing = not name_text.strip()
        self._set_invalid(self.edit_name, bool(name_text) and name_missing)
        if name_missing:
            valid = False

        for widget in (
            self.edit_ip,
            self.edit_mask_custom,
            self.edit_gateway,
            self.edit_dns_primary,
            self.edit_dns_secondary,
        ):
            self._set_invalid(widget, False)

        if self.radio_static.isChecked():
            ip_text = self.edit_ip.text().strip()
            gateway_text = self.edit_gateway.text().strip()
            ip_invalid = not network_controller.validate_ipv4(ip_text)
            gateway_invalid = not network_controller.validate_ipv4(gateway_text)
            self._set_invalid(self.edit_ip, bool(ip_text) and ip_invalid)
            self._set_invalid(self.edit_gateway, bool(gateway_text) and gateway_invalid)
            valid = valid and not ip_invalid and not gateway_invalid

            if self.combo_mask.currentIndex() == 3:
                mask_text = self.edit_mask_custom.text().strip()
                mask_invalid = not network_controller.validate_subnet_mask(mask_text)
                self._set_invalid(self.edit_mask_custom, bool(mask_text) and mask_invalid)
                valid = valid and not mask_invalid

        if self.radio_dns_manual.isChecked():
            primary_text = self.edit_dns_primary.text().strip()
            primary_invalid = not network_controller.validate_ipv4(primary_text)
            secondary_text = self.edit_dns_secondary.text().strip()
            secondary_invalid = bool(secondary_text) and not network_controller.validate_ipv4(secondary_text)
            self._set_invalid(self.edit_dns_primary, bool(primary_text) and primary_invalid)
            self._set_invalid(self.edit_dns_secondary, secondary_invalid)
            valid = valid and not primary_invalid and not secondary_invalid

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
                if not network_controller.validate_subnet_mask(self.edit_mask_custom.text()):
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
