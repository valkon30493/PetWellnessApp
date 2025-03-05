import sys
import sqlite3
from hashlib import sha256
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget, \
    QMessageBox


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login - Veterinary Management Software")

        # Create widgets for the login form
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

        # Container widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def authenticate_user(self):
        username = self.username_input.text()
        password = self.password_input.text()

        # Connect to SQLite database
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()

        # Hash the entered password
        hashed_password = sha256(password.encode()).hexdigest()

        # Query the database for the user
        cursor.execute('''
            SELECT users.user_id, roles.role_name FROM users
            JOIN roles ON users.role_id = roles.role_id
            WHERE users.username = ? AND users.password = ?
        ''', (username, hashed_password))

        user = cursor.fetchone()
        conn.close()

        if user:
            user_id, role_name = user
            QMessageBox.information(self, "Login Successful", f"Welcome, {role_name}!")
            # Proceed to the next part of the application based on the role
            self.open_main_window(role_name)
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password")

    def open_main_window(self, role_name):
        # Here you would navigate to the main application window
        # and load specific features based on `role_name`
        print(f"Navigating to the main application with role: {role_name}")


# Run the application
app = QApplication(sys.argv)
login_window = LoginWindow()
login_window.show()
sys.exit(app.exec())
