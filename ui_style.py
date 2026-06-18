"""Shared visual styling for NetSwitch Qt widgets."""

FONT_FAMILY = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"'

WINDOW_BG = "#F4F7FA"
SURFACE = "rgba(255, 255, 255, 232)"
SURFACE_STRONG = "#FFFFFF"
SURFACE_SOFT = "#F8FAFC"
BORDER = "#DCE3EA"
BORDER_FOCUS = "#68A7FF"
TEXT = "#1D2733"
TEXT_SECONDARY = "#687483"
TEXT_MUTED = "#9AA5B1"
ACCENT = "#0A84FF"
ACCENT_HOVER = "#0071E3"
ACCENT_SOFT = "#EAF4FF"
SUCCESS = "#34C759"
SUCCESS_SOFT = "#E8F7ED"
WARNING = "#D97706"
WARNING_SOFT = "#FFF4DC"
DANGER = "#D92D20"
DANGER_SOFT = "#FFF0EE"


COMMON_QSS = f"""
QWidget {{
    font-family: {FONT_FAMILY};
    color: {TEXT};
    font-size: 12px;
}}

QDialog {{
    background: {WINDOW_BG};
}}

QLabel {{
    color: {TEXT};
}}

QLabel[muted="true"] {{
    color: {TEXT_SECONDARY};
}}

QFrame#glassPanel,
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QGroupBox {{
    margin-top: 12px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: {TEXT_SECONDARY};
}}

QLineEdit,
QComboBox {{
    min-height: 32px;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0 10px;
    background: rgba(255, 255, 255, 238);
    color: {TEXT};
}}

QLineEdit:focus,
QComboBox:focus {{
    border: 1px solid {BORDER_FOCUS};
    background: #FFFFFF;
}}

QLineEdit[invalid="true"] {{
    border: 1px solid {DANGER};
    background: {DANGER_SOFT};
}}

QLineEdit:read-only {{
    color: {TEXT_SECONDARY};
    background: {SURFACE_SOFT};
}}

QComboBox::drop-down {{
    width: 24px;
    border: none;
}}

QPushButton {{
    min-height: 32px;
    border-radius: 8px;
    padding: 0 14px;
    border: 1px solid {BORDER};
    background: rgba(255, 255, 255, 230);
    color: {TEXT};
}}

QPushButton:hover {{
    background: #FFFFFF;
    border-color: #C9D3DF;
}}

QPushButton:disabled {{
    color: {TEXT_MUTED};
    background: #EEF2F6;
    border-color: #E1E7EE;
}}

QPushButton#primaryButton {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton#primaryButton:disabled {{
    background: #C8D7E8;
    border-color: #C8D7E8;
    color: rgba(255, 255, 255, 190);
}}

QPushButton#dangerButton {{
    color: {DANGER};
    background: {DANGER_SOFT};
    border-color: #F2C8C2;
}}

QPushButton#dangerButton:hover {{
    background: #FFE4E0;
}}

QPushButton#dangerButton:disabled {{
    color: {TEXT_MUTED};
    background: #EEF2F6;
    border-color: #E1E7EE;
}}

QPushButton#textButton {{
    background: transparent;
    border-color: transparent;
    color: {TEXT_SECONDARY};
}}

QPushButton#textButton:hover {{
    background: rgba(255, 255, 255, 170);
    border-color: {BORDER};
}}

QRadioButton,
QCheckBox {{
    spacing: 8px;
    color: {TEXT};
}}

QRadioButton::indicator,
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}
"""

# 菜单样式抽出独立片段，让 COMMON_QSS 和 MENU_QSS 共享同一份，避免重复维护两份。
_MENU_RULES = f"""
QMenu {{
    background: {SURFACE_STRONG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background: {ACCENT_SOFT};
    color: {TEXT};
}}
"""

# 主样式表附带菜单样式
COMMON_QSS = COMMON_QSS + _MENU_RULES

# 托盘菜单专用样式：QWidget 字体规则 + 菜单本体；不挂表单/按钮等控件样式
MENU_QSS = f"""
QWidget {{
    font-family: {FONT_FAMILY};
    color: {TEXT};
    font-size: 12px;
}}
""" + _MENU_RULES


def polish(widget):
    """Re-apply style after dynamic property changes."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def apply_common_style(widget):
    widget.setStyleSheet(COMMON_QSS)
