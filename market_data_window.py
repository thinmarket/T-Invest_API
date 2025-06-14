# market_data_window.py
import asyncio
import threading
import grpc
import logging
from typing import Optional, Dict, Any, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox,
    QScrollArea, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QMetaObject, Q_ARG, QTimer, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from tinkoff.invest import (
    AsyncClient, Client,
    MarketDataRequest, SubscribeOrderBookRequest, SubscribeTradesRequest,
    SubscribeLastPriceRequest, SubscriptionAction, OrderBookInstrument,
    TradeInstrument, LastPriceInstrument, MarketDataResponse, Quotation,
    SecurityTradingStatus, InstrumentIdType, TradeDirection
)
from tinkoff.invest.exceptions import AioRequestError
from datetime import datetime
import pytz
import traceback
from analytics_window import AnalyticsWindow  # Добавлен импорт

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

def quotation_to_float(quotation: Quotation) -> float:
    return float(f"{quotation.units}.{abs(quotation.nano):09d}")

class MarketDataStreamer(QObject):
    raw_data_received = pyqtSignal(str)
    data_updated = pyqtSignal(dict)
    stream_error = pyqtSignal(str)
    connection_status = pyqtSignal(bool)

    def __init__(self, token: str, figi: str):
        super().__init__()
        self.token = token
        self.figi = figi
        self.client: Optional[AsyncClient] = None
        self.stream_thread: Optional[threading.Thread] = None
        self.running = False
        self.last_update_time: Optional[datetime] = None

    async def check_instrument_status(self):
        try:
            async with AsyncClient(self.token) as client:
                status = await client.market_data.get_trading_status(instrument_id=self.figi)
                if status.trading_status != SecurityTradingStatus.SECURITY_TRADING_STATUS_NORMAL_TRADING:
                    raise Exception(f"Instrument not available for trading. Status: {status.trading_status.name}")
                return True
        except Exception as e:
            logger.error(f"Instrument status check failed: {e}")
            raise

    async def _run_stream(self):
        try:
            async with AsyncClient(self.token) as client:
                self.client = client
                logger.info("Client created, setting up stream...")
                self.connection_status.emit(True)

                async def request_iterator():
                    try:
                        yield MarketDataRequest(
                            subscribe_order_book_request=SubscribeOrderBookRequest(
                                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                                instruments=[OrderBookInstrument(
                                    instrument_id=self.figi,
                                    depth=50
                                )],
                            )
                        )
                        yield MarketDataRequest(
                            subscribe_trades_request=SubscribeTradesRequest(
                                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                                instruments=[TradeInstrument(
                                    instrument_id=self.figi,
                                )],
                            )
                        )
                        yield MarketDataRequest(
                            subscribe_last_price_request=SubscribeLastPriceRequest(
                                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                                instruments=[LastPriceInstrument(
                                    instrument_id=self.figi,
                                )],
                            )
                        )

                        while self.running:
                            await asyncio.sleep(0.1)
                            yield MarketDataRequest()

                    except Exception as e:
                        logger.error(f"Request iterator error: {e}")
                        raise

                stream = client.market_data_stream.market_data_stream(request_iterator())

                async for response in stream:
                    if not self.running:
                        break

                    raw_data = f"--- Raw Market Data Response ---\n{response}\n\n"
                    self.raw_data_received.emit(raw_data)

                    try:
                        data = {}

                        if hasattr(response, 'orderbook') and response.orderbook is not None:
                            order_book = response.orderbook
                            asks = []
                            for ask in order_book.asks:
                                if ask.price is not None:
                                    asks.append({
                                        "price": quotation_to_float(ask.price),
                                        "quantity": ask.quantity
                                    })
                            bids = []
                            for bid in order_book.bids:
                                if bid.price is not None:
                                    bids.append({
                                        "price": quotation_to_float(bid.price),
                                        "quantity": bid.quantity
                                    })

                            data["order_book"] = {
                                "figi": order_book.figi,
                                "depth": order_book.depth,
                                "is_consistent": order_book.is_consistent,
                                "asks": sorted(asks, key=lambda x: x["price"]),
                                "bids": sorted(bids, key=lambda x: x["price"], reverse=True),
                                "time": order_book.time.astimezone(MOSCOW_TZ).strftime("%H:%M:%S.%f")[:-3]
                            }

                        if hasattr(response, 'trade') and response.trade is not None:
                            trade = response.trade
                            if trade.price is not None:
                                trade_time = trade.time.astimezone(MOSCOW_TZ)
                                trade_data = {
                                    "price": quotation_to_float(trade.price),
                                    "quantity": trade.quantity,
                                    "direction": trade.direction,
                                    "time": trade_time.strftime("%H:%M:%S.%f")[:-3]  # Формат: 10:34:38.634
                                }
                                data["trade"] = trade_data

                        if hasattr(response, 'last_price') and response.last_price is not None:
                            last_price = response.last_price
                            if last_price.price is not None:
                                data["last_price"] = {
                                    "price": quotation_to_float(last_price.price),
                                    "time": last_price.time.astimezone(MOSCOW_TZ).strftime("%H:%M:%S.%f")[:-3]
                                }

                        if data:
                            self.data_updated.emit(data)

                    except Exception as e:
                        logger.error(f"Error processing market data: {e}")
                        self.raw_data_received.emit(f"Error processing data: {e}\n")

        except asyncio.CancelledError:
            logger.info("Stream was cancelled")
        except grpc.RpcError as e:
            error_msg = f"gRPC error: {e.code().name} - {e.details()}"
            logger.error(error_msg)
            self.stream_error.emit(error_msg)
        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            logger.error(error_msg)
            self.stream_error.emit(error_msg)
        finally:
            logger.info("Stream stopped")
            self.connection_status.emit(False)

    def start_stream(self):
        if not self.running:
            self.running = True
            self.last_update_time = None

            def run_async_loop(loop):
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._run_stream())

            loop = asyncio.new_event_loop()
            self.stream_thread = threading.Thread(target=run_async_loop, args=(loop,))
            self.stream_thread.daemon = True
            self.stream_thread.start()

    def stop_stream(self):
        if self.running:
            self.running = False
            logger.info("Stopping stream...")

class MarketDataWindow(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("СТАКАН И СДЕЛКИ (DEBUG MODE)")
        self.parent = parent
        self.token = None
        self.selected_figi = None
        self.streamer = None
        self.trade_volumes_by_price: Dict[float, Dict[str, int]] = {}
        self.current_asks: List[Dict[str, Any]] = []
        self.current_bids: List[Dict[str, Any]] = []
        self.last_price_value: Optional[float] = None
        self.class_codes = []
        self.ticker_map = {}
        self.analytics_window = AnalyticsWindow(self)  # Создаем окно аналитики
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 15, 10, 10)
        main_layout.setSpacing(15)

        select_layout = QHBoxLayout()
        self.class_code_combo = QComboBox()
        self.class_code_combo.setPlaceholderText("Выберите площадку")
        self.class_code_combo.currentIndexChanged.connect(self.on_class_code_changed)
        self.class_code_combo.setMaximumWidth(200)

        self.ticker_combo = QComboBox()
        self.ticker_combo.setPlaceholderText("Выберите тикер")
        self.ticker_combo.setMaximumWidth(250)

        self.stream_button = QPushButton("Запустить стрим")
        self.stream_button.clicked.connect(self.toggle_streaming)
        self.stream_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # Добавляем кнопку для открытия аналитики
        self.analytics_button = QPushButton("Аналитика")
        self.analytics_button.clicked.connect(self.open_analytics_window)
        self.analytics_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)

        select_layout.addWidget(QLabel("Площадка:"))
        select_layout.addWidget(self.class_code_combo)
        select_layout.addWidget(QLabel("Тикер:"))
        select_layout.addWidget(self.ticker_combo)
        select_layout.addWidget(self.stream_button)
        select_layout.addWidget(self.analytics_button)  # Добавляем кнопку аналитики
        main_layout.addLayout(select_layout)

        splitter = QSplitter(Qt.Vertical)

        order_book_group = QGroupBox("Стакан и Сделки")
        order_book_layout = QVBoxLayout(order_book_group)
        self.order_book_table = QTableWidget()
        self.order_book_table.setColumnCount(5)
        self.order_book_table.setHorizontalHeaderLabels([
            "Объем Покупок",
            "Заявки Покупка",
            "Цена",
            "Заявки Продажа",
            "Объем Продаж"
        ])
        self.order_book_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.order_book_table.verticalHeader().setVisible(False)
        self.order_book_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.order_book_table.setSelectionMode(QTableWidget.NoSelection)
        order_book_layout.addWidget(self.order_book_table)
        splitter.addWidget(order_book_group)

        raw_data_group = QGroupBox("Сырые данные (DEBUG)")
        raw_data_layout = QVBoxLayout(raw_data_group)
        self.raw_data_text_edit = QTextEdit()
        self.raw_data_text_edit.setReadOnly(True)
        self.raw_data_text_edit.setPlaceholderText("Здесь будут отображаться сырые данные из стрима...")
        raw_data_layout.addWidget(self.raw_data_text_edit)
        splitter.addWidget(raw_data_group)

        main_layout.addWidget(splitter)

        self.status_label = QLabel("Статус: Не активен")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #FF5252;
                font-weight: bold;
            }
        """)
        main_layout.addWidget(self.status_label)

    def open_analytics_window(self):
        """Открывает окно аналитики"""
        if self.analytics_window:
            self.analytics_window.show()
            self.analytics_window.raise_()
            self.analytics_window.activateWindow()

    def set_token(self, token):
        self.token = token
        if self.token:
            threading.Thread(target=self._load_class_codes_in_thread, daemon=True).start()

    def _load_class_codes_in_thread(self):
        class_codes = []
        ticker_map = {}
        try:
            with Client(self.token) as client:
                all_instruments = []
                shares_response = client.instruments.shares()
                all_instruments.extend(shares_response.instruments)
                futures_response = client.instruments.futures()
                all_instruments.extend(futures_response.instruments)

                codes = set()
                for inst in all_instruments:
                    if inst.class_code in ('TQBR', 'SPBFUT') and inst.api_trade_available_flag:
                        codes.add(inst.class_code)
                        ticker_map[(inst.ticker, inst.class_code)] = inst

                class_codes = sorted(list(codes))
                QMetaObject.invokeMethod(self, 'on_instruments_loaded',
                                       Qt.QueuedConnection,
                                       Q_ARG(list, class_codes),
                                       Q_ARG(dict, ticker_map))

        except Exception as e:
            self.parent.show_info(f"Ошибка загрузки площадок: {str(e)}")
            QMetaObject.invokeMethod(self, 'on_instruments_loaded',
                                   Qt.QueuedConnection,
                                   Q_ARG(list, []),
                                   Q_ARG(dict, {}))

    @pyqtSlot(list, dict)
    def on_instruments_loaded(self, class_codes, ticker_map):
        self.class_code_combo.clear()
        self.class_codes = class_codes
        self.ticker_map = ticker_map
        self.class_code_combo.addItems(self.class_codes)
        if self.class_codes:
            self.on_class_code_changed(0)

    def on_class_code_changed(self, idx):
        if idx < 0 or not self.token or not self.class_codes:
            self.ticker_combo.clear()
            return
        class_code = self.class_codes[idx]
        self.ticker_combo.clear()
        tickers = [t for (t, c) in self.ticker_map if c == class_code]
        self.ticker_combo.addItems(sorted(tickers))

    def toggle_streaming(self):
        if self.streamer and self.streamer.running:
            self.stop_streaming()
        else:
            self.start_streaming()

    def start_streaming(self):
        class_code = self.class_code_combo.currentText()
        ticker = self.ticker_combo.currentText()
        if not class_code or not ticker:
            self.parent.show_info("Выберите площадку и тикер")
            return
        if not self.token:
            self.parent.show_info("Сначала авторизуйтесь")
            return

        instrument = self.ticker_map.get((ticker, class_code))
        if not instrument:
            self.parent.show_info(f"Инструмент {ticker} на площадке {class_code} не найден.")
            return

        figi = instrument.figi
        instrument_id_to_use = instrument.uid if instrument.uid else figi

        if not instrument_id_to_use:
            self.parent.show_info(f"Не удалось получить instrument_id/FIGI для инструмента {ticker}.")
            return

        try:
            with Client(self.token) as client:
                trading_status_response = client.market_data.get_trading_status(
                    instrument_id=instrument_id_to_use
                )
                if trading_status_response.trading_status != SecurityTradingStatus.SECURITY_TRADING_STATUS_NORMAL_TRADING:
                    status_name = SecurityTradingStatus(trading_status_response.trading_status).name
                    self.parent.show_info(f"Инструмент {ticker} ({class_code}) в статусе: {status_name}. Стриминг невозможен.")
                    return
        except Exception as e:
            self.parent.show_info(f"Ошибка при проверке статуса инструмента: {str(e)}")
            return

        if self.streamer:
            self.streamer.stop_stream()

        self.streamer = MarketDataStreamer(self.token, instrument_id_to_use)
        self.streamer.raw_data_received.connect(self.on_raw_data_received)
        self.streamer.data_updated.connect(self.on_data_updated)
        self.streamer.stream_error.connect(self.display_error)
        self.streamer.connection_status.connect(self.update_connection_status)

        self.trade_volumes_by_price.clear()
        self.current_asks = []
        self.current_bids = []
        self.last_price_value = None
        self.order_book_table.clearContents()
        self.order_book_table.setRowCount(0)

        self.streamer.start_stream()
        self.stream_button.setText("Остановить стрим")
        self.stream_button.setStyleSheet("background-color: #f44336; color: white;")
        self.status_label.setText(f"Статус: Активен ({ticker} {class_code})")
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.raw_data_text_edit.clear()

    def stop_streaming(self):
        if self.streamer:
            self.streamer.stop_stream()
            self.stream_button.setText("Запустить стрим")
            self.stream_button.setStyleSheet("background-color: #4CAF50; color: white;")
            self.status_label.setText("Статус: Не активен")
            self.status_label.setStyleSheet("color: #FF5252;")

    @pyqtSlot(str)
    def on_raw_data_received(self, raw_data: str):
        self.raw_data_text_edit.append(raw_data)
        cursor = self.raw_data_text_edit.textCursor()
        cursor.movePosition(cursor.End)
        self.raw_data_text_edit.setTextCursor(cursor)

    @pyqtSlot(dict)
    def on_data_updated(self, data: dict):
        logger.debug(f"on_data_updated called with data keys: {data.keys()}")

        if "order_book" in data:
            self.current_asks = data["order_book"]["asks"]
            self.current_bids = data["order_book"]["bids"]
            logger.debug(f"Updated current_asks (len={len(self.current_asks)}) and current_bids (len={len(self.current_bids)})")

        if "trade" in data:
            trade_data = data["trade"]
            price = trade_data["price"]
            quantity = trade_data["quantity"]
            direction = trade_data["direction"]
            
            if price not in self.trade_volumes_by_price:
                self.trade_volumes_by_price[price] = {"buy": 0, "sell": 0}
            
            if direction == TradeDirection.TRADE_DIRECTION_BUY:
                self.trade_volumes_by_price[price]["buy"] += quantity
            elif direction == TradeDirection.TRADE_DIRECTION_SELL:
                self.trade_volumes_by_price[price]["sell"] += quantity
            
            logger.debug(f"Processed trade: price={price}, quantity={quantity}, direction={direction.name}. Total buy/sell volume for {price}: {self.trade_volumes_by_price[price]}")
            
            # Передаем данные о сделке в окно аналитики
            if hasattr(self, 'analytics_window') and self.analytics_window:
                self.analytics_window.update_trades_data(trade_data)

        if "last_price" in data:
            self.last_price_value = data["last_price"]["price"]
            logger.debug(f"Updated last_price_value: {self.last_price_value}")
        
        self._update_order_book_table_display()

    def _update_order_book_table_display(self):
        self.order_book_table.clearContents()
        
        logger.debug(f"Redrawing table. current_asks: {self.current_asks}")
        logger.debug(f"Redrawing table. current_bids: {self.current_bids}")
        logger.debug(f"Redrawing table. trade_volumes_by_price: {self.trade_volumes_by_price}")
        logger.debug(f"Redrawing table. last_price_value: {self.last_price_value}")

        all_prices_set = set()
        for ask in self.current_asks:
            all_prices_set.add(ask["price"])
        for bid in self.current_bids:
            all_prices_set.add(bid["price"])
        for price in self.trade_volumes_by_price.keys():
            all_prices_set.add(price)

        all_prices = sorted(list(all_prices_set), reverse=True) 

        self.order_book_table.setRowCount(len(all_prices))
        
        for row_idx, price in enumerate(all_prices):
            buy_volume = self.trade_volumes_by_price.get(price, {}).get("buy", "")
            item_buy_volume = QTableWidgetItem(str(buy_volume) if buy_volume != "" else "")
            item_buy_volume.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_buy_volume.setForeground(QColor(Qt.darkGreen))
            self.order_book_table.setItem(row_idx, 0, item_buy_volume)

            bid_quantity = ""
            for bid in self.current_bids:
                if bid["price"] == price:
                    bid_quantity = str(bid["quantity"])
                    break
            item_bid_quantity = QTableWidgetItem(bid_quantity if bid_quantity != "" else "")
            item_bid_quantity.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_bid_quantity.setForeground(QColor(Qt.green))
            self.order_book_table.setItem(row_idx, 1, item_bid_quantity)
            
            price_str = f"{price:.3f}" if int(price * 1000) % 10 != 0 else f"{price:.2f}"
            item_price = QTableWidgetItem(price_str)
            item_price.setTextAlignment(Qt.AlignCenter)
            self.order_book_table.setItem(row_idx, 2, item_price)

            ask_quantity = ""
            for ask in self.current_asks:
                if ask["price"] == price:
                    ask_quantity = str(ask["quantity"])
                    break
            item_ask_quantity = QTableWidgetItem(ask_quantity if ask_quantity != "" else "")
            item_ask_quantity.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_ask_quantity.setForeground(QColor(Qt.red))
            self.order_book_table.setItem(row_idx, 3, item_ask_quantity)

            sell_volume = self.trade_volumes_by_price.get(price, {}).get("sell", "")
            item_sell_volume = QTableWidgetItem(str(sell_volume) if sell_volume != "" else "")
            item_sell_volume.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_sell_volume.setForeground(QColor(Qt.darkRed))
            self.order_book_table.setItem(row_idx, 4, item_sell_volume)

            if self.last_price_value is not None and self.last_price_value == price:
                for col in range(self.order_book_table.columnCount()):
                    item = self.order_book_table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor("#0d1a08"))

        total_buy_volume = sum(v.get("buy", 0) for v in self.trade_volumes_by_price.values())
        total_sell_volume = sum(v.get("sell", 0) for v in self.trade_volumes_by_price.values())

        current_row_count = self.order_book_table.rowCount()
        self.order_book_table.setRowCount(current_row_count + 1)
        
        total_label_item = QTableWidgetItem("ИТОГО")
        total_label_item.setTextAlignment(Qt.AlignCenter)
        font = total_label_item.font()
        font.setBold(True)
        total_label_item.setFont(font)
        self.order_book_table.setItem(current_row_count, 2, total_label_item)

        total_buy_volume_item = QTableWidgetItem(str(total_buy_volume))
        total_buy_volume_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_buy_volume_item.setForeground(QColor(Qt.darkGreen))
        total_buy_volume_item.setFont(font)
        self.order_book_table.setItem(current_row_count, 0, total_buy_volume_item)

        total_sell_volume_item = QTableWidgetItem(str(total_sell_volume))
        total_sell_volume_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        total_sell_volume_item.setForeground(QColor(Qt.darkRed))
        total_sell_volume_item.setFont(font)
        self.order_book_table.setItem(current_row_count, 4, total_sell_volume_item)

        self.order_book_table.setItem(current_row_count, 1, QTableWidgetItem(""))
        self.order_book_table.setItem(current_row_count, 3, QTableWidgetItem(""))
        
        logger.debug(f"Table update finished. Rows: {self.order_book_table.rowCount()}")

    @pyqtSlot(str)
    def display_error(self, message: str):
        logger.error(f"Stream error: {message}")
        QMessageBox.critical(self, "Ошибка стриминга", message)
        self.stop_streaming()

    @pyqtSlot(bool)
    def update_connection_status(self, is_connected: bool):
        current_text = self.status_label.text()
        if is_connected:
            self.status_label.setText(f"{current_text.split('(')[0]}(Подключено)")
        else:
            self.status_label.setText(f"{current_text.split('(')[0]}(Отключено)")

    def closeEvent(self, event):
        if self.streamer:
            self.streamer.stop_stream()
        if hasattr(self, 'analytics_window') and self.analytics_window:
            self.analytics_window.close()
        super().closeEvent(event)
