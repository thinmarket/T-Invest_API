import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from tinkoff.invest import Client, CandleInterval
from datetime import datetime, timezone, timedelta
import pytz

class MarketDataStreamer(QObject):
    data_updated = pyqtSignal(str, dict)  # instrument_uid, data dict

    def __init__(self, token, instruments):
        super().__init__()
        self.token = token
        self.instruments = instruments  # {uid: {ticker, class_code}}
        self.running = False
        self.threads = {}

    def start(self):
        self.running = True
        for uid in self.instruments:
            if uid not in self.threads:
                t = threading.Thread(target=self.stream_instrument, args=(uid,), daemon=True)
                self.threads[uid] = t
                t.start()

    def stop(self):
        self.running = False

    def stream_instrument(self, uid):
        # Для простоты: обновляем данные раз в 1 секунду (имитация стриминга)
        while self.running:
            try:
                with Client(self.token) as client:
                    # Последняя цена
                    last_price = client.market_data.get_last_prices(instrument_id=[uid])
                    price = None
                    time = None
                    if last_price.last_prices:
                        p = last_price.last_prices[0].price
                        price = p.units + p.nano / 1e9
                        time = last_price.last_prices[0].time
                    # Минутные свечи за день (только объем, оборот убран)
                    now = datetime.now(timezone.utc)
                    msk = pytz.timezone('Europe/Moscow')
                    msk_now = now.astimezone(msk)
                    msk_midnight = msk_now.replace(hour=0, minute=0, second=0, microsecond=0)
                    utc_midnight = msk_midnight.astimezone(timezone.utc)
                    candles = client.market_data.get_candles(
                        instrument_id=uid,
                        from_=utc_midnight,
                        to=now,
                        interval=CandleInterval.CANDLE_INTERVAL_1_MIN
                    )
                    volume = 0
                    if candles.candles:
                        for c in candles.candles:
                            v = c.volume
                            volume += v
                    else:
                        volume = None

                    # Время по Москве
                    msk_time = None
                    if time:
                        msk_time = time.astimezone(msk).strftime('%d.%m.%Y %H:%M:%S')
                    data = {
                        'price': price,
                        'volume': volume,
                        'time': msk_time
                    }
                    self.data_updated.emit(uid, data)
            except Exception as e:
                self.data_updated.emit(uid, {'error': str(e)})
            import time as t
            t.sleep(1)

class TickerWindow(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("ПОИСК ИНСТРУМЕНТОВ")
        self.parent = parent
        self.init_ui()
        self.class_codes = []
        self.ticker_map = {}  # (ticker, class_code) -> instrument
        self.selected_instruments = {}  # uid -> {ticker, class_code}
        self.streamer = None

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(15)

        select_layout = QHBoxLayout()
        self.class_code_combo = QComboBox()
        self.class_code_combo.setPlaceholderText("Выберите площадку")
        self.class_code_combo.currentIndexChanged.connect(self.on_class_code_changed)
        self.class_code_combo.setMaximumWidth(200) # Ограничиваем ширину

        self.ticker_combo = QComboBox()
        self.ticker_combo.setPlaceholderText("Выберите тикер")
        self.ticker_combo.setMaximumWidth(250) # Ограничиваем ширину

        self.add_button = QPushButton("Добавить")
        self.add_button.clicked.connect(self.add_ticker)

        select_layout.addWidget(QLabel("Площадка:"))
        select_layout.addWidget(self.class_code_combo)
        select_layout.addWidget(QLabel("Тикер:"))
        select_layout.addWidget(self.ticker_combo)
        select_layout.addWidget(self.add_button)

        # Изменено количество столбцов на 4 (убран "Оборот (день)")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "Тикер", "Последняя цена", "Объем (день)", "Время (МСК)"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) # Разрешаем интерактивное изменение размеров

        # Кнопка удаления
        self.remove_button = QPushButton("Удалить")
        self.remove_button.clicked.connect(self.remove_ticker)

        layout.addLayout(select_layout)
        layout.addWidget(self.table)
        layout.addWidget(self.remove_button)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_class_codes()

    def load_class_codes(self):
        self.class_code_combo.clear()
        self.class_codes = []
        self.ticker_map = {}
        if not self.parent.token:
            return
        try:
            with Client(self.parent.token) as client:
                all_instruments = []
                # Получаем акции
                shares_response = client.instruments.shares()
                all_instruments.extend(shares_response.instruments)
                # Получаем фьючерсы
                futures_response = client.instruments.futures()
                all_instruments.extend(futures_response.instruments)

                codes = set()
                for inst in all_instruments:
                    if inst.class_code in ('TQBR', 'SPBFUT'):
                        codes.add(inst.class_code)
                        self.ticker_map[(inst.ticker, inst.class_code)] = inst

                self.class_codes = sorted(list(codes))
                self.class_code_combo.addItems(self.class_codes)

        except Exception as e:
            self.parent.show_info(f"Ошибка загрузки площадок: {str(e)}")

    def on_class_code_changed(self, idx):
        if idx < 0 or not self.parent.token:
            return
        class_code = self.class_codes[idx]
        self.ticker_combo.clear()
        tickers = [t for (t, c) in self.ticker_map if c == class_code]
        self.ticker_combo.addItems(sorted(tickers))

    def add_ticker(self):
        class_code = self.class_code_combo.currentText()
        ticker = self.ticker_combo.currentText()
        if not class_code or not ticker:
            self.parent.show_info("Выберите площадку и тикер")
            return
        if not self.parent.token:
            self.parent.show_info("Сначала авторизуйтесь")
            return
        instrument = self.ticker_map.get((ticker, class_code))
        if not instrument:
            self.parent.show_info("Инструмент не найден")
            return
        uid = instrument.uid
        if uid in self.selected_instruments:
            self.parent.show_info("Этот тикер уже добавлен")
            return
        self.selected_instruments[uid] = {'ticker': ticker, 'class_code': class_code}
        self.update_table()
        self.start_streaming()
        self.parent.show_info(f"Добавлен {ticker} ({class_code})")

    def update_table(self):
        self.table.setRowCount(len(self.selected_instruments))
        for row, (uid, info) in enumerate(self.selected_instruments.items()):
            self.table.setItem(row, 0, QTableWidgetItem(info['ticker']))
            self.table.setItem(row, 1, QTableWidgetItem("-"))
            self.table.setItem(row, 2, QTableWidgetItem("-"))
            self.table.setItem(row, 3, QTableWidgetItem("-")) # Время (МСК)
            # self.table.setItem(row, 4, QTableWidgetItem("-")) # Оборот убран

    def start_streaming(self):
        if self.streamer:
            self.streamer.stop()
        self.streamer = MarketDataStreamer(self.parent.token, self.selected_instruments)
        self.streamer.data_updated.connect(self.on_data_update)
        self.streamer.start()

    def on_data_update(self, uid, data):
        if uid not in self.selected_instruments:
            return
        row = list(self.selected_instruments.keys()).index(uid)
        if 'error' in data:
            self.table.setItem(row, 1, QTableWidgetItem(f"Ошибка: {data['error']}"))
            return
        # Форматирование объема
        def format_number(val):
            if val is None:
                return "-"
            try:
                return f"{int(round(val)):,}".replace(",", " ")
            except Exception:
                return str(val)
        price_str = str(data['price']) if data['price'] is not None else "-"
        volume_str = format_number(data['volume'])
        # turnover_str = format_number(data['turnover']) # Оборот убран
        self.table.setItem(row, 1, QTableWidgetItem(price_str))
        self.table.setItem(row, 2, QTableWidgetItem(volume_str))
        # self.table.setItem(row, 3, QTableWidgetItem(turnover_str)) # Оборот убран
        self.table.setItem(row, 3, QTableWidgetItem(data['time'] if data['time'] is not None else "-"))

    def remove_ticker(self):
        selected = self.table.currentRow()
        if selected < 0 or selected >= len(self.selected_instruments):
            self.parent.show_info("Выделите строку для удаления")
            return
        uid = list(self.selected_instruments.keys())[selected]
        info = self.selected_instruments[uid]
        del self.selected_instruments[uid]
        self.update_table()
        self.start_streaming()
        self.parent.show_info(f"Удалён {info['ticker']} ({info['class_code']})")
