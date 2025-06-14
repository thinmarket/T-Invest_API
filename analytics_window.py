import time 
import threading
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QScrollArea,
    QSplitter, QProgressBar, QLineEdit, QSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QMetaObject, Q_ARG, QTimer, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from tinkoff.invest import TradeDirection
import pytz

class AnalyticsWindow(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("АНАЛИТИКА СДЕЛОК")
        self.parent = parent
        self.large_buys = []
        self.large_sells = []
        self.trade_timestamps = []  # Хранит (timestamp, broker_time)
        self.all_trades_history = []
        
        # Таймеры для сброса счетчиков
        self.current_minute = None
        self.current_5min_interval = None
        self.broker_timezone = pytz.timezone('Europe/Moscow')
        
        self.init_ui()
        self.reset_timers()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 15, 10, 10)
        main_layout.setSpacing(15)

        # Секция фильтров
        filter_layout = QHBoxLayout()
        
        self.trade_threshold_input = QLineEdit("1000")
        self.trade_threshold_input.setPlaceholderText("Порог объема для сделок")
        self.trade_threshold_input.setMaximumWidth(200)
        
        self.apply_filters_button = QPushButton("Применить фильтры")
        self.apply_filters_button.clicked.connect(self._filter_and_display_data)
        
        self.clear_history_button = QPushButton("Очистить историю")
        self.clear_history_button.clicked.connect(self.clear_history)
        self.clear_history_button.setStyleSheet("background-color: #f44336; color: white;")

        filter_layout.addWidget(QLabel("Порог сделок:"))
        filter_layout.addWidget(self.trade_threshold_input)
        filter_layout.addWidget(self.apply_filters_button)
        filter_layout.addWidget(self.clear_history_button)
        filter_layout.addStretch()

        main_layout.addLayout(filter_layout)

        # Таблицы сделок
        trades_splitter = QSplitter(Qt.Horizontal)
        
        buy_group = QGroupBox("Крупные Покупки")
        buy_layout = QVBoxLayout(buy_group)
        self.large_buys_table = QTableWidget(0, 3)
        self.large_buys_table.setHorizontalHeaderLabels(["Цена", "Объем", "Время"])
        self.large_buys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.large_buys_table.verticalHeader().setVisible(False)
        self.large_buys_table.setEditTriggers(QTableWidget.NoEditTriggers)
        buy_layout.addWidget(self.large_buys_table)
        trades_splitter.addWidget(buy_group)

        sell_group = QGroupBox("Крупные Продажи")
        sell_layout = QVBoxLayout(sell_group)
        self.large_sells_table = QTableWidget(0, 3)
        self.large_sells_table.setHorizontalHeaderLabels(["Цена", "Объем", "Время"])
        self.large_sells_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.large_sells_table.verticalHeader().setVisible(False)
        self.large_sells_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sell_layout.addWidget(self.large_sells_table)
        trades_splitter.addWidget(sell_group)

        main_layout.addWidget(trades_splitter)

        # Группа для счетчиков сделок
        counters_group = QGroupBox("Счетчики сделок")
        counters_layout = QVBoxLayout()

        # 1. Сделок за текущую минуту
        self.minute_layout = QHBoxLayout()
        self.minute_bar = QProgressBar()
        self.minute_bar.setRange(0, 1000)  # Максимум 1000 сделок/минуту
        self.minute_bar.setFormat("Текущая минута: %v")
        self.minute_bar.setStyleSheet("QProgressBar::chunk { background-color: #2196F3; }")
        self.minute_label = QLabel("0")
        self.minute_label.setMinimumWidth(80)
        self.minute_layout.addWidget(self.minute_bar)
        self.minute_layout.addWidget(self.minute_label)

        # 2. Сделок за текущую 5-минутку
        self.five_min_layout = QHBoxLayout()
        self.five_min_bar = QProgressBar()
        self.five_min_bar.setRange(0, 5000)  # Максимум 5000 сделок/5 минут
        self.five_min_bar.setFormat("Текущие 5 минут: %v")
        self.five_min_bar.setStyleSheet("QProgressBar::chunk { background-color: #9C27B0; }")
        self.five_min_label = QLabel("0")
        self.five_min_label.setMinimumWidth(80)
        self.five_min_layout.addWidget(self.five_min_bar)
        self.five_min_layout.addWidget(self.five_min_label)

        # Таймеры
        self.time_layout = QHBoxLayout()
        self.current_time_label = QLabel("Время брокера: --:--:--")
        self.next_reset_label = QLabel("Сброс через: --:--")
        self.time_layout.addWidget(self.current_time_label)
        self.time_layout.addWidget(self.next_reset_label)

        counters_layout.addLayout(self.minute_layout)
        counters_layout.addLayout(self.five_min_layout)
        counters_layout.addLayout(self.time_layout)
        counters_group.setLayout(counters_layout)
        main_layout.addWidget(counters_group)

        # Таймер для обновления UI
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui_time)
        self.ui_timer.start(1000)  # Обновляем каждую секунду

    def reset_timers(self):
        """Сбрасывает счетчики в зависимости от интервала"""
        now = datetime.now(self.broker_timezone)
        
        # Обновляем текущую минуту
        new_minute = now.replace(second=0, microsecond=0)
        if self.current_minute != new_minute:
            self.current_minute = new_minute
            self.minute_bar.setValue(0)
            self.minute_label.setText("0")
        
        # Обновляем 5-минутный интервал (каждые 5 минут)
        new_5min = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
        if self.current_5min_interval != new_5min:
            self.current_5min_interval = new_5min
            self.five_min_bar.setValue(0)
            self.five_min_label.setText("0")
        
        # Рассчитываем время следующего сброса
        next_minute = self.current_minute + timedelta(minutes=1)
        next_5min = self.current_5min_interval + timedelta(minutes=5)
        self.next_reset_time = min(next_minute, next_5min)
        
        self.update_ui_time()

    def update_ui_time(self):
        """Обновляет отображение времени и проверяет сброс счетчиков"""
        now = datetime.now(self.broker_timezone)
        self.current_time_label.setText(f"Время брокера: {now.strftime('%H:%M:%S')}")
        
        # Проверяем, не настало ли время сброса
        if now >= self.next_reset_time:
            self.reset_timers()
        
        # Обновляем оставшееся время до сброса
        time_left = self.next_reset_time - now
        self.next_reset_label.setText(
            f"Сброс через: {time_left.seconds // 60}:{time_left.seconds % 60:02d}"
        )

    def update_trade_counters(self, broker_time):
        """Обновляет счетчики сделок на основе времени брокера"""
        broker_time = broker_time.astimezone(self.broker_timezone)
        
        # Считаем сделки за текущую минуту
        if broker_time.replace(second=0, microsecond=0) == self.current_minute:
            minute_trades = sum(
                1 for _, bt in self.trade_timestamps 
                if bt.astimezone(self.broker_timezone).replace(second=0, microsecond=0) == self.current_minute
            )
            self.minute_bar.setValue(minute_trades)
            self.minute_label.setText(str(minute_trades))
        
        # Считаем сделки за текущую 5-минутку
        if broker_time.replace(minute=(broker_time.minute // 5) * 5, second=0, microsecond=0) == self.current_5min_interval:
            five_min_trades = sum(
                1 for _, bt in self.trade_timestamps 
                if bt.astimezone(self.broker_timezone).replace(
                    minute=(bt.minute // 5) * 5, second=0, microsecond=0
                ) == self.current_5min_interval
            )
            self.five_min_bar.setValue(five_min_trades)
            self.five_min_label.setText(str(five_min_trades))

    def clear_history(self):
        """Полностью очищает историю и сбрасывает счетчики"""
        self.large_buys = []
        self.large_sells = []
        self.all_trades_history = []
        self.trade_timestamps = []
        
        self.large_buys_table.setRowCount(0)
        self.large_sells_table.setRowCount(0)
        
        self.reset_timers()
        self.minute_bar.setValue(0)
        self.minute_label.setText("0")
        self.five_min_bar.setValue(0)
        self.five_min_label.setText("0")

    def _filter_and_display_data(self):
        try:
            trade_threshold = int(self.trade_threshold_input.text())
        except ValueError:
            trade_threshold = 0

        self._filter_and_display_large_trades(trade_threshold)

    def _filter_and_display_large_trades(self, threshold):
        self.large_buys = []
        self.large_sells = []

        for trade in self.all_trades_history:
            if trade['quantity'] >= threshold:
                if trade["direction"] == TradeDirection.TRADE_DIRECTION_BUY:
                    self.large_buys.append(trade)
                elif trade["direction"] == TradeDirection.TRADE_DIRECTION_SELL:
                    self.large_sells.append(trade)
        
        max_entries = 50
        if len(self.large_buys) > max_entries:
            self.large_buys = self.large_buys[-max_entries:]
        if len(self.large_sells) > max_entries:
            self.large_sells = self.large_sells[-max_entries:]

        self.display_large_trades()

    def display_large_trades(self):
        self.large_buys_table.setRowCount(len(self.large_buys))
        for row, trade in enumerate(self.large_buys):
            self.large_buys_table.setItem(row, 0, QTableWidgetItem(f"{trade['price']:.3f}"))
            self.large_buys_table.setItem(row, 1, QTableWidgetItem(str(trade['quantity'])))
            self.large_buys_table.setItem(row, 2, QTableWidgetItem(trade['time']))
            for col in range(3):
                item = self.large_buys_table.item(row, col)
                if item:
                    item.setBackground(QColor(40, 60, 40))
                    item.setForeground(QColor(Qt.green))

        self.large_sells_table.setRowCount(len(self.large_sells))
        for row, trade in enumerate(self.large_sells):
            self.large_sells_table.setItem(row, 0, QTableWidgetItem(f"{trade['price']:.3f}"))
            self.large_sells_table.setItem(row, 1, QTableWidgetItem(str(trade['quantity'])))
            self.large_sells_table.setItem(row, 2, QTableWidgetItem(trade['time']))
            for col in range(3):
                item = self.large_sells_table.item(row, col)
                if item:
                    item.setBackground(QColor(60, 40, 40))
                    item.setForeground(QColor(Qt.red))

    @pyqtSlot(dict)
    def update_trades_data(self, trade_data: dict):
        """Обрабатывает новую сделку"""
        try:
            trade_time_str = trade_data['time']  # Формат: "10:34:38.634"
            
            # Парсим время без даты
            current_time = datetime.strptime(trade_time_str, "%H:%M:%S.%f").replace(
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day
            ).astimezone(self.broker_timezone)
            
            self.trade_timestamps.append((time.time(), current_time))
            self.all_trades_history.append(trade_data)
            
            self.update_trade_counters(current_time)
            
            try:
                threshold = int(self.trade_threshold_input.text())
                if trade_data['quantity'] >= threshold:
                    self._filter_and_display_large_trades(threshold)
            except ValueError:
                pass
            
        except Exception as e:
            print(f"Error processing trade data: {e}")
