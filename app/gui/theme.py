"""Dark theme stylesheet for the trading bot GUI."""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
}

QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #58a6ff;
}

QLabel {
    color: #c9d1d9;
    font-size: 13px;
}

QLabel#header {
    font-size: 18px;
    font-weight: bold;
    color: #f0f6fc;
}

QLabel#value {
    font-size: 15px;
    font-weight: 600;
    color: #f0f6fc;
}

QLabel#badge_paper {
    background-color: #1f6feb;
    color: white;
    padding: 3px 10px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}

QLabel#badge_live {
    background-color: #da3633;
    color: white;
    padding: 3px 10px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}

QLabel#status_ok {
    color: #3fb950;
    font-weight: bold;
}

QLabel#status_down {
    color: #da3633;
    font-weight: bold;
}

QLabel#signal_up {
    color: #3fb950;
    font-weight: bold;
}

QLabel#signal_down {
    color: #da3633;
    font-weight: bold;
}

QLabel#signal_neutral {
    color: #8b949e;
}

QPushButton {
    background-color: #238636;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #2ea043;
}

QPushButton:pressed {
    background-color: #196c2e;
}

QPushButton#stop_btn {
    background-color: #da3633;
}

QPushButton#stop_btn:hover {
    background-color: #f85149;
}

QPushButton:disabled {
    background-color: #21262d;
    color: #484f58;
}

QTableWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 4px;
    gridline-color: #21262d;
    selection-background-color: #1f6feb;
}

QTableWidget::item {
    padding: 4px 8px;
}

QHeaderView::section {
    background-color: #161b22;
    color: #8b949e;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 12px;
}

QTextEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 4px;
    color: #8b949e;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 4px;
}

QTabWidget::pane {
    border: 1px solid #30363d;
    background-color: #0d1117;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #161b22;
    color: #8b949e;
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:selected {
    color: #f0f6fc;
    border-bottom: 2px solid #58a6ff;
}

QTabBar::tab:hover {
    color: #c9d1d9;
}

QScrollBar:vertical {
    background-color: #0d1117;
    width: 8px;
}

QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 6px 8px;
    color: #c9d1d9;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #58a6ff;
}

QComboBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 6px 8px;
    color: #c9d1d9;
}

QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #30363d;
    background-color: #0d1117;
}

QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #238636;
}
"""
