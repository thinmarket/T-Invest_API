from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

def setup_palette(app):
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    app.setStyleSheet("""
        QGroupBox {
            border: 2px solid #4CAF50;
            border-radius: 5px;
            margin-top: 0.5em;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px;
            color: #4CAF50;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 120px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QLineEdit {
            background-color: #333;
            color: white;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 8px;
            selection-background-color: #4CAF50;
        }
        QLabel {
            color: white;
        }
        QScrollArea {
            border: none;
        }
        QScrollBar:vertical {
            border: none;
            background: #252525;
            width: 10px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #4CAF50;
            min-height: 20px;
            border-radius: 4px;
        }
        #headerFrame {
            background-color: #1E1E1E;
            border-bottom: 2px solid #4CAF50;
        }
    """)