from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


DARK_STYLESHEET = """
QWidget {
    background: #20242b;
    color: #e7eaf0;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #1b1f25;
}
QTabWidget::pane {
    border: 1px solid #3a414c;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background: #292f38;
    border: 1px solid #3a414c;
    padding: 8px 14px;
    margin-right: 3px;
}
QTabBar::tab:selected {
    background: #394454;
    border-bottom-color: #6ba8ff;
}
QGroupBox {
    border: 1px solid #3a414c;
    border-radius: 7px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QListWidget, QTableWidget {
    background: #15191f;
    color: #edf0f5;
    border: 1px solid #46505e;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #3d6595;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {
    border: 1px solid #75a9e8;
}
QPushButton {
    background: #354253;
    border: 1px solid #52647a;
    border-radius: 5px;
    padding: 7px 13px;
}
QPushButton:hover {
    background: #40536b;
}
QPushButton:pressed {
    background: #2b3542;
}
QPushButton:disabled {
    color: #858d98;
    background: #272c33;
    border-color: #363d47;
}
QCheckBox, QRadioButton {
    spacing: 7px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 15px;
    height: 15px;
}
QScrollArea {
    border: none;
}
QStatusBar {
    background: #171b21;
    color: #b8c1ce;
}
QHeaderView::section {
    background: #2b323c;
    color: #e7eaf0;
    padding: 6px;
    border: none;
}
"""


def apply_qt_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    application.setFont(QFont("Sans Serif", 10))
    application.setStyleSheet(DARK_STYLESHEET)
