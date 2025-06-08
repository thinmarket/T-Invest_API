import sys
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QSplitter, QFrame, QSizePolicy,
                            QGroupBox, QScrollArea)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from styles import setup_palette
from connection_window import ConnectionWindow
from ticker_window import TickerWindow

class TinkoffInvestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("T-Invest API")
        self.setGeometry(100, 100, 1400, 900)
        self.token = None
        self.init_ui()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_frame.setFixedHeight(80)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.title_label = QLabel("T-INVEST API")
        self.title_label.setFont(QFont("Arial", 20, QFont.Bold))
        self.title_label.setStyleSheet("color: #4CAF50;")
        
        self.status_label = QLabel("Не авторизован")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setStyleSheet("color: #FF5252;")
        
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Arial", 14))
        self.update_time()
        
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        header_layout.addWidget(self.time_label)
        main_layout.addWidget(header_frame)
        
        # Main content
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)
        
        # Left panel (connection)
        self.connection_window = ConnectionWindow(self)
        
        # Right panel (info and instruments)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # Info group
        self.info_group = QGroupBox("ИНФОРМАЦИЯ")
        self.info_label = QLabel("Введите API токен для начала работы")
        self.info_label.setWordWrap(True)
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.info_label)
        self.info_group.setLayout(info_layout)
        
        # Instruments group
        self.ticker_window = TickerWindow(self)
        self.ticker_window.setVisible(False)
        
        right_layout.addWidget(self.info_group)
        right_layout.addWidget(self.ticker_window)
        right_layout.addStretch()
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.connection_window)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        content_layout.addWidget(splitter)
        main_layout.addWidget(content_widget)
        
    def update_time(self):
        current_time = datetime.now().strftime("%H:%M:%S")
        current_date = datetime.now().strftime("%d.%m.%Y")
        self.time_label.setText(f"{current_date} | {current_time}")
        
    def show_info(self, message):
        self.info_label.setText(message)
        
    def update_status(self, authenticated, message=""):
        if authenticated:
            self.status_label.setText("Авторизован")
            self.status_label.setStyleSheet("color: #4CAF50;")
            self.ticker_window.setVisible(True)
        else:
            self.status_label.setText("Не авторизован")
            self.status_label.setStyleSheet("color: #FF5252;")
            self.ticker_window.setVisible(False)
        if message:
            self.show_info(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    setup_palette(app)
    window = TinkoffInvestApp()
    window.show()
    sys.exit(app.exec_())