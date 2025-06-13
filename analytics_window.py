import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox,
    QScrollArea, QTextEdit, QSplitter, QProgressBar, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QMetaObject, Q_ARG, QTimer, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from tinkoff.invest import TradeDirection
import time

class AnalyticsWindow(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("АНАЛИТИКА СДЕЛОК")
        self.parent = parent
        self.large_buys = []
        self.large_sells = []
        self.trade_timestamps = []  # Хранит временные метки сделок
        self.all_trades_history = [] # Хранит всю историю сделок для перефильтрации
        self.min_trade_rate = float('inf')  # Минимальная скорость
        self.max_trade_rate = 0      # Максимальная скорость
        self.window_size = 5         # Окно измерения скорости (в секундах)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 15, 10, 10)
        main_layout.setSpacing(15)

        # Секция для порога объема крупных сделок
        threshold_layout = QHBoxLayout()
        self.trade_threshold_input = QLineEdit("1000") # Значение по умолчанию
        self.trade_threshold_input.setPlaceholderText("Порог объема для крупных сделок (например, 1000)")
        self.trade_threshold_input.setMaximumWidth(250)
        self.apply_threshold_button = QPushButton("Применить фильтр")
        self.apply_threshold_button.clicked.connect(self._filter_and_display_large_trades)

        threshold_layout.addWidget(QLabel("Порог объема:"))
        threshold_layout.addWidget(self.trade_threshold_input)
        threshold_layout.addWidget(self.apply_threshold_button)
        threshold_layout.addStretch()

        main_layout.addLayout(threshold_layout)

        # Таблица крупных покупок
        buy_group = QGroupBox("Крупные Покупки")
        buy_layout = QVBoxLayout(buy_group)
        self.large_buys_table = QTableWidget(0, 3)
        self.large_buys_table.setHorizontalHeaderLabels(["Цена", "Объем", "Время"])
        self.large_buys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.large_buys_table.verticalHeader().setVisible(False)
        self.large_buys_table.setEditTriggers(QTableWidget.NoEditTriggers)
        buy_layout.addWidget(self.large_buys_table)
        main_layout.addWidget(buy_group)

        # Таблица крупных продаж
        sell_group = QGroupBox("Крупные Продажи")
        sell_layout = QVBoxLayout(sell_group)
        self.large_sells_table = QTableWidget(0, 3)
        self.large_sells_table.setHorizontalHeaderLabels(["Цена", "Объем", "Время"])
        self.large_sells_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.large_sells_table.verticalHeader().setVisible(False)
        self.large_sells_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sell_layout.addWidget(self.large_sells_table)
        main_layout.addWidget(sell_group)
        
        main_layout.addStretch()

        # QProgressBar для скорости сделок
        self.velocity_bar = QProgressBar()
        self.velocity_bar.setRange(0, 100)
        self.velocity_bar.setFormat("Скорость сделок: %v%")
        self.velocity_bar.setStyleSheet("""
            QProgressBar {
                text-align: center;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        main_layout.addWidget(self.velocity_bar)

    @pyqtSlot(dict)
    def update_trades_data(self, trade_data: dict):
        # Всегда добавляем сделку в полную историю
        self.all_trades_history.append(trade_data)

        # Обновляем скорость сделок, используя все сделки
        self.trade_timestamps.append(time.time())  # Фиксируем время сделки
        self.update_trade_rate_velocity()          # Пересчитываем скорость

        # После добавления сделки, перефильтруем и отобразим крупные сделки
        self._filter_and_display_large_trades()

    def calculate_current_trade_rate(self):
        now = time.time()
        # Считаем сделки за последние `window_size` секунд
        recent_trades = [t for t in self.trade_timestamps if now - t <= self.window_size]
        # Удаляем старые временные метки, чтобы список не рос бесконечно
        self.trade_timestamps = [t for t in self.trade_timestamps if now - t <= self.window_size]
        return len(recent_trades) / self.window_size if self.window_size > 0 else 0 # Сделок в секунду

    def update_trade_rate_velocity(self):
        current_rate = self.calculate_current_trade_rate()
        
        # Обновляем минимумы/максимумы
        if current_rate < self.min_trade_rate:
            self.min_trade_rate = current_rate
        if current_rate > self.max_trade_rate:
            self.max_trade_rate = current_rate
        
        # Нормализуем до шкалы 0-100
        if self.max_trade_rate != self.min_trade_rate:
            velocity = 100 * (current_rate - self.min_trade_rate) / (self.max_trade_rate - self.min_trade_rate)
        else:
            velocity = 0
        
        self.display_velocity(velocity)  # Отображаем значение
        return velocity

    def display_velocity(self, velocity):
        self.velocity_bar.setValue(int(velocity))

    def _filter_and_display_large_trades(self):
        try:
            threshold = int(self.trade_threshold_input.text()) # Получаем порог из поля ввода
        except ValueError:
            threshold = 0 # Если ввод некорректен, используем 0

        self.large_buys = []
        self.large_sells = []

        for trade in self.all_trades_history:
            if trade['quantity'] >= threshold:
                if trade["direction"] == TradeDirection.TRADE_DIRECTION_BUY:
                    self.large_buys.append(trade)
                elif trade["direction"] == TradeDirection.TRADE_DIRECTION_SELL:
                    self.large_sells.append(trade)
        
        # Ограничим количество записей для наглядности (можно скорректировать)
        max_entries = 50
        if len(self.large_buys) > max_entries:
            self.large_buys = self.large_buys[-max_entries:]
        if len(self.large_sells) > max_entries:
            self.large_sells = self.large_sells[-max_entries:]

        self.display_large_trades()

    def display_large_trades(self):
        # Заполняем таблицу покупок
        self.large_buys_table.setRowCount(len(self.large_buys))
        for row, trade in enumerate(self.large_buys):
            self.large_buys_table.setItem(row, 0, QTableWidgetItem(f"{trade['price']:.3f}"))
            self.large_buys_table.setItem(row, 1, QTableWidgetItem(str(trade['quantity'])))
            self.large_buys_table.setItem(row, 2, QTableWidgetItem(trade['time']))
            # Зеленый цвет для покупок
            for col in range(3):
                item = self.large_buys_table.item(row, col)
                if item:
                    item.setBackground(QColor(40, 60, 40)) # Темно-зеленый
                    item.setForeground(QColor(Qt.green))

        # Заполняем таблицу продаж
        self.large_sells_table.setRowCount(len(self.large_sells))
        for row, trade in enumerate(self.large_sells):
            self.large_sells_table.setItem(row, 0, QTableWidgetItem(f"{trade['price']:.3f}"))
            self.large_sells_table.setItem(row, 1, QTableWidgetItem(str(trade['quantity'])))
            self.large_sells_table.setItem(row, 2, QTableWidgetItem(trade['time']))
            # Красный цвет для продаж
            for col in range(3):
                item = self.large_sells_table.item(row, col)
                if item:
                    item.setBackground(QColor(60, 40, 40)) # Темно-красный
                    item.setForeground(QColor(Qt.red)) 