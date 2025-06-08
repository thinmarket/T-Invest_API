from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QScrollArea, QGroupBox, 
                            QFormLayout)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from tinkoff.invest import Client

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
        auth_group = QGroupBox("АВТОРИЗАЦИЯ")
        auth_layout = QHBoxLayout()
        
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Введите ваш Tinkoff API токен")
        self.token_input.setEchoMode(QLineEdit.Password)
        
        self.auth_button = QPushButton("ПОДКЛЮЧИТЬСЯ")
        self.auth_button.clicked.connect(self.connect_to_api)
        
        auth_layout.addWidget(self.token_input)
        auth_layout.addWidget(self.auth_button)
        auth_group.setLayout(auth_layout)
        
        # Accounts group
        self.accounts_group = QGroupBox("МОИ СЧЕТА")
        self.accounts_group.setVisible(False)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.accounts_widget = QWidget()
        self.accounts_layout = QVBoxLayout(self.accounts_widget)
        scroll.setWidget(self.accounts_widget)
        
        self.accounts_group.setLayout(QVBoxLayout())
        self.accounts_group.layout().addWidget(scroll)
        
        layout.addWidget(auth_group)
        layout.addWidget(self.accounts_group)
        layout.addStretch()
    
    def connect_to_api(self):
        token = self.token_input.text().strip()
        if not token:
            self.parent.show_info("Ошибка: Введите API токен")
            return
            
        try:
            with Client(token) as client:
                # Test connection
                client.users.get_accounts()
                self.parent.token = token
                self.parent.update_status(True, "Успешное подключение")
                self.show_accounts(client)
                
        except Exception as e:
            self.parent.update_status(False, f"Ошибка подключения: {str(e)}")
            self.accounts_group.setVisible(False)
    
    def show_accounts(self, client):
        # Clear previous accounts
        while self.accounts_layout.count():
            item = self.accounts_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            self.parent.show_info("Нет доступных счетов")
            return
            
        for account in accounts.accounts:
            group = QGroupBox(account.name)
            form = QFormLayout()
            
            form.addRow("ID:", QLabel(account.id))
            form.addRow("Тип:", QLabel(str(account.type).split('.')[-1]))
            form.addRow("Статус:", QLabel(str(account.status).split('.')[-1]))
            
            group.setLayout(form)
            self.accounts_layout.addWidget(group)
        
        self.accounts_group.setVisible(True)