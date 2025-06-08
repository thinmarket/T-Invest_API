from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QScrollArea, QGroupBox, 
                            QFormLayout)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from tinkoff.invest import Client

class TickerWindow(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("ПОИСК ИНСТРУМЕНТОВ")
        self.parent = parent
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(15)
        
        # Search panel
        search_layout = QHBoxLayout()
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Введите тикер (например SBER)")
        
        self.search_button = QPushButton("ПОИСК")
        self.search_button.clicked.connect(self.search_instruments)
        
        search_layout.addWidget(self.ticker_input)
        search_layout.addWidget(self.search_button)
        
        # Results area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        scroll.setWidget(self.results_widget)
        
        layout.addLayout(search_layout)
        layout.addWidget(scroll)
    
    def search_instruments(self):
        ticker = self.ticker_input.text().strip().upper()
        if not ticker:
            self.parent.show_info("Введите тикер для поиска")
            return
            
        if not self.parent.token:
            self.parent.show_info("Сначала авторизуйтесь")
            return
            
        try:
            with Client(self.parent.token) as client:
                instruments = client.instruments.find_instrument(query=ticker)
                
                # Clear previous results
                while self.results_layout.count():
                    item = self.results_layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                
                if not instruments.instruments:
                    self.parent.show_info(f"Инструменты по тикеру '{ticker}' не найдены")
                    return
                
                self.parent.show_info(f"Найдено {len(instruments.instruments)} инструментов")
                
                for instrument in instruments.instruments:
                    group = QGroupBox(instrument.name)
                    form = QFormLayout()
                    
                    form.addRow("Тикер:", QLabel(instrument.ticker))
                    form.addRow("FIGI:", QLabel(instrument.figi))
                    form.addRow("Тип:", QLabel(str(instrument.instrument_type).split('.')[-1]))
                    form.addRow("Класс:", QLabel(instrument.class_code))
                    
                    group.setLayout(form)
                    self.results_layout.addWidget(group)
                
        except Exception as e:
            self.parent.show_info(f"Ошибка поиска: {str(e)}")