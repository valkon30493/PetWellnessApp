# login_screen.py
import sqlite3
from hashlib import sha256
from PySide6.QtWidgets import (
    QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QWidget, QMessageBox
)
from PySide6.QtCore import Signal

class LoginWindow(QMainWindow):
    login_successful = Signal(str, str)  # username, role

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login - Veterinary Management Software")

        # Widgets
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.authenticate_user)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Please log in"))
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def authenticate_user(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        hashed_password = sha256(password.encode()).hexdigest()

        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT users.user_id, roles.role_name
            FROM users
            JOIN roles ON users.role_id = roles.role_id
            WHERE users.username = ? AND users.password = ?
        ''', (username, hashed_password))
        user = cursor.fetchone()
        conn.close()

        if user:
            user_id, role_name = user
            self.login_successful.emit(username, role_name)
            self.close()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password")
