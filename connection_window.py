from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QScrollArea, QGroupBox, 
                            QFormLayout)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from tinkoff.invest import Client
from account_info_window import AccountInfoWindow # Добавлено

class ConnectionWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Auth group
        self.auth_group = QGroupBox("АВТОРИЗАЦИЯ")
        auth_layout = QHBoxLayout()
        
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Введите ваш Tinkoff API токен")
        self.token_input.setEchoMode(QLineEdit.Password)
        
        self.auth_button = QPushButton("ПОДКЛЮЧИТЬСЯ")
        self.auth_button.clicked.connect(self.connect_to_api)
        
        auth_layout.addWidget(self.token_input)
        auth_layout.addWidget(self.auth_button)
        self.auth_group.setLayout(auth_layout)
        
        # Создаем экземпляр AccountInfoWindow
        self.account_info_window = AccountInfoWindow(self.parent) # Передаем parent из main.py
        self.account_info_window.setVisible(False) # Скрываем до авторизации
        
        layout.addWidget(self.auth_group)
        layout.addWidget(self.account_info_window) # Добавляем напрямую
        layout.addStretch()
    
    def connect_to_api(self):
        token = self.token_input.text().strip()
        if not token:
            self.parent.show_info("Ошибка: Введите API токен")
            return
            
        try:
            with Client(token) as client:
                # Test connection
                accounts_response = client.users.get_accounts() # Получаем ответ с аккаунтами
                
                if not accounts_response.accounts:
                    self.parent.show_info("Нет доступных счетов")
                    self.parent.update_status(False)
                    self.account_info_window.setVisible(False) # Скрыть кабинет
                    return

                # Используем первый найденный аккаунт по умолчанию
                first_account_id = accounts_response.accounts[0].id

                self.parent.token = token # Сохраняем токен в главном окне
                self.parent.update_status(True, "Успешное подключение")
                
                # Скрываем блок авторизации и показываем блок с информацией о счете
                self.auth_group.setVisible(False)
                self.account_info_window.setVisible(True) # Показываем кабинет

                # Передаем токен и account_id в AccountInfoWindow для загрузки данных
                self.account_info_window.set_account_info(token, first_account_id)
                
        except Exception as e:
            self.parent.update_status(False, f"Ошибка подключения: {str(e)}") # ИСПРАВЛЕНО: Используем update_status
            self.account_info_window.setVisible(False) # Скрыть кабинет
