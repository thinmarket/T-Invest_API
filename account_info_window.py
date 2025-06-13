import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from tinkoff.invest import Client, AccountType, InstrumentIdType # Добавлено InstrumentIdType

class AccountInfoWindow(QGroupBox):
    # Сигнал для обновления UI из потока
    data_loaded = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__("МОЙ КАБИНЕТ")
        self.parent = parent
        self.token = None
        self.account_id = None
        self.init_ui()
        
        # Подключаем сигнал к слоту обновления UI
        self.data_loaded.connect(self.update_ui_with_data)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 15, 10, 10)
        main_layout.setSpacing(15)

        # --- Секция "Информация о счете" ---
        self.account_group = QGroupBox("Информация о счете")
        self.account_form_layout = QFormLayout()
        self.account_id_label = QLabel("-")
        self.account_type_label = QLabel("-")
        self.account_name_label = QLabel("-")
        self.account_status_label = QLabel("-")
        self.account_form_layout.addRow("ID счета:", self.account_id_label)
        self.account_form_layout.addRow("Тип счета:", self.account_type_label)
        self.account_form_layout.addRow("Название:", self.account_name_label)
        self.account_form_layout.addRow("Статус:", self.account_status_label)
        self.account_group.setLayout(self.account_form_layout)
        main_layout.addWidget(self.account_group)

        # --- Секция "Статус пользователя" ---
        self.user_status_group = QGroupBox("Статус пользователя")
        self.user_status_form_layout = QFormLayout()
        self.prem_status_label = QLabel("-")
        self.qual_status_label = QLabel("-")
        self.tariff_label = QLabel("-")
        self.qualified_for_label = QLabel("-")
        self.qualified_for_label.setWordWrap(True) # Добавлено: перенос строк

        self.user_status_form_layout.addRow("Премиум:", self.prem_status_label)
        self.user_status_form_layout.addRow("Квалиф. инвестор:", self.qual_status_label)
        self.user_status_form_layout.addRow("Тариф:", self.tariff_label)
        self.user_status_form_layout.addRow("Доступно:", self.qualified_for_label)
        self.user_status_group.setLayout(self.user_status_form_layout)
        main_layout.addWidget(self.user_status_group)


        # --- Секция "Портфель" ---
        self.portfolio_group = QGroupBox("Портфель")
        self.portfolio_form_layout = QFormLayout()
        self.total_amount_shares_label = QLabel("-")
        self.total_amount_bonds_label = QLabel("-")
        self.total_amount_etf_label = QLabel("-")
        self.total_amount_currencies_label = QLabel("-")
        self.total_amount_futures_label = QLabel("-")
        self.total_amount_total_label = QLabel("-")
        self.expected_yield_label = QLabel("-")
        
        self.portfolio_form_layout.addRow("Акции:", self.total_amount_shares_label)
        self.portfolio_form_layout.addRow("Облигации:", self.total_amount_bonds_label)
        self.portfolio_form_layout.addRow("ETF:", self.total_amount_etf_label)
        self.portfolio_form_layout.addRow("Валюта:", self.total_amount_currencies_label)
        self.portfolio_form_layout.addRow("Фьючерсы:", self.total_amount_futures_label)
        self.portfolio_form_layout.addRow("ИТОГО:", self.total_amount_total_label)
        self.portfolio_form_layout.addRow("Доходность (%):", self.expected_yield_label)

        self.portfolio_group.setLayout(self.portfolio_form_layout)
        main_layout.addWidget(self.portfolio_group)

        # --- Секция "Позиции" ---
        self.positions_group = QGroupBox("Позиции")
        self.positions_table = QTableWidget(0, 5) # Тикер, Количество, Средняя цена, Текущая цена, Доходность
        self.positions_table.setHorizontalHeaderLabels([
            "Тикер", "Кол-во", "Средняя цена", "Текущая цена", "Доходность"
        ])
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) # Изменено на Interactive
        
        positions_layout = QVBoxLayout()
        positions_scroll = QScrollArea()
        positions_scroll.setWidgetResizable(True)
        positions_scroll.setWidget(self.positions_table)
        positions_layout.addWidget(positions_scroll)
        self.positions_group.setLayout(positions_layout)
        main_layout.addWidget(self.positions_group)

        main_layout.addStretch()
        self.set_data_placeholders()

    def set_data_placeholders(self):
        """Устанавливает плейсхолдеры для данных."""
        self.account_id_label.setText("-")
        self.account_type_label.setText("-")
        self.account_name_label.setText("-")
        self.account_status_label.setText("-")

        self.prem_status_label.setText("-")
        self.qual_status_label.setText("-")
        self.tariff_label.setText("-")
        self.qualified_for_label.setText("-")

        self.total_amount_shares_label.setText("-")
        self.total_amount_bonds_label.setText("-")
        self.total_amount_etf_label.setText("-")
        self.total_amount_currencies_label.setText("-")
        self.total_amount_futures_label.setText("-")
        self.total_amount_total_label.setText("-")
        self.expected_yield_label.setText("-")
        self.positions_table.setRowCount(0)

    def set_account_info(self, token, account_id):
        """Устанавливает токен и ID счета и запускает загрузку данных."""
        self.token = token
        self.account_id = account_id
        if self.token and self.account_id:
            self.parent.show_info(f"Загрузка данных для счета: {self.account_id}...")
            self.set_data_placeholders() # Очищаем старые данные
            threading.Thread(target=self._load_data_in_thread, daemon=True).start()
        else:
            self.parent.show_info("Токен или ID счета не установлены.")
            self.set_data_placeholders()

    def _load_data_in_thread(self):
        """Загружает данные в отдельном потоке."""
        data = {}
        try:
            with Client(self.token) as client:
                # Информация о счете
                accounts_response = client.users.get_accounts()
                account = next((a for a in accounts_response.accounts if a.id == self.account_id), None)
                if account:
                    account_type_str = ""
                    # Используем константы для более читаемого типа счета
                    if account.type == AccountType.ACCOUNT_TYPE_TINKOFF: 
                        account_type_str = "Брокерский счет"
                    elif account.type == AccountType.ACCOUNT_TYPE_TINKOFF_IIS: 
                        account_type_str = "ИИС"
                    elif account.type == AccountType.ACCOUNT_TYPE_INVEST_BOX: 
                        account_type_str = "Инвесткопилка"
                    else:
                        account_type_str = str(account.type).split('.')[-1] # Fallback
                        
                    data['account_info'] = {
                        'id': account.id,
                        'type': account_type_str,
                        'name': account.name,
                        'status': str(account.status).split('.')[-1]
                    }
                else:
                    self.parent.show_info(f"Счет {self.account_id} не найден.")
                    data['account_info'] = None

                # Информация о пользователе
                user_info_response = client.users.get_info()
                data['user_info'] = {
                    'prem_status': "Да" if user_info_response.prem_status else "Нет",
                    'qual_status': "Да" if user_info_response.qual_status else "Нет",
                    'tariff': user_info_response.tariff if user_info_response.tariff else "-",
                    'qualified_for_work_with': ", ".join(user_info_response.qualified_for_work_with) if user_info_response.qualified_for_work_with else "Нет"
                }

                # Портфель
                portfolio_response = client.operations.get_portfolio(account_id=self.account_id)
                data['portfolio'] = {
                    'total_amount_shares': self._format_money(portfolio_response.total_amount_shares),
                    'total_amount_bonds': self._format_money(portfolio_response.total_amount_bonds),
                    'total_amount_etf': self._format_money(portfolio_response.total_amount_etf),
                    'total_amount_currencies': self._format_money(portfolio_response.total_amount_currencies),
                    'total_amount_futures': self._format_money(portfolio_response.total_amount_futures),
                    'total_amount_portfolio': self._format_money(portfolio_response.total_amount_portfolio),
                    'expected_yield': self._format_quotation(portfolio_response.expected_yield)
                }

                # Позиции
                positions = []
                for p in portfolio_response.positions: 
                    ticker = ""
                    current_price = ""
                    try:
                        # Попробуем найти инструмент по UID
                        instrument_response = client.instruments.get_instrument_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID, id=p.instrument_uid) 
                        ticker = instrument_response.instrument.ticker if instrument_response.instrument.ticker else instrument_response.instrument.name
                        if not ticker: # Если тикер не найден, пробуем имя
                             ticker = instrument_response.instrument.name
                    except Exception:
                        # Если не удалось получить инфу по UID, пробуем FIGI
                        try:
                            instrument_response = client.instruments.get_instrument_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=p.figi)
                            ticker = instrument_response.instrument.ticker if instrument_response.instrument.ticker else instrument_response.instrument.name
                            if not ticker:
                                ticker = instrument_response.instrument.name
                        except Exception:
                            ticker = p.figi if p.figi else "Неизвестно" # Если ничего не помогло, используем FIGI или "Неизвестно"
                    
                    if p.current_price:
                        current_price = self._format_money(p.current_price)
                    else:
                        current_price = "-"

                    positions.append({
                        'ticker': ticker,
                        'quantity': self._format_quotation(p.quantity),
                        'average_position_price': self._format_money(p.average_position_price_fifo), 
                        'current_price': current_price,
                        'expected_yield': self._format_quotation(p.expected_yield_fifo)
                    })
                data['positions'] = positions

        except Exception as e:
            self.parent.show_info(f"Ошибка загрузки данных счета: {str(e)}")
            data['error'] = str(e)
        
        self.data_loaded.emit(data)

    def update_ui_with_data(self, data):
        """Обновляет элементы UI данными."""
        if 'error' in data:
            self.set_data_placeholders()
            return

        # Обновление информации о счете
        account_info = data.get('account_info')
        if account_info:
            self.account_id_label.setText(account_info['id'])
            self.account_type_label.setText(account_info['type'])
            self.account_name_label.setText(account_info['name'])
            self.account_status_label.setText(account_info['status'])

        # Обновление статуса пользователя
        user_info = data.get('user_info')
        if user_info:
            self.prem_status_label.setText(user_info['prem_status'])
            self.qual_status_label.setText(user_info['qual_status'])
            self.tariff_label.setText(user_info['tariff'])
            self.qualified_for_label.setText(user_info['qualified_for_work_with'])

        # Обновление портфеля
        portfolio = data.get('portfolio')
        if portfolio:
            self.total_amount_shares_label.setText(portfolio['total_amount_shares'])
            self.total_amount_bonds_label.setText(portfolio['total_amount_bonds'])
            self.total_amount_etf_label.setText(portfolio['total_amount_etf'])
            self.total_amount_currencies_label.setText(portfolio['total_amount_currencies'])
            self.total_amount_futures_label.setText(portfolio['total_amount_futures'])
            self.total_amount_total_label.setText(portfolio['total_amount_portfolio'])
            self.expected_yield_label.setText(portfolio['expected_yield'])

        # Обновление позиций
        positions = data.get('positions', [])
        self.positions_table.setRowCount(len(positions))
        for row, pos in enumerate(positions):
            self.positions_table.setItem(row, 0, QTableWidgetItem(pos['ticker']))
            self.positions_table.setItem(row, 1, QTableWidgetItem(pos['quantity']))
            self.positions_table.setItem(row, 2, QTableWidgetItem(pos['average_position_price']))
            self.positions_table.setItem(row, 3, QTableWidgetItem(pos['current_price']))
            self.positions_table.setItem(row, 4, QTableWidgetItem(pos['expected_yield']))

    def _format_money(self, money_value):
        if money_value is None:
            return "-"
        return f"{money_value.units}.{money_value.nano / 1e9:.2f} {money_value.currency}"

    def _format_quotation(self, quotation_value):
        if quotation_value is None:
            return "-"
        return f"{quotation_value.units}.{quotation_value.nano / 1e9:.2f}"