import sys
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget, QPushButton


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Veterinary Management Software")

        # Main layout and widgets
        layout = QVBoxLayout()

        label = QLabel("Welcome to the Veterinary Management Software")
        button = QPushButton("Click Me")

        layout.addWidget(label)
        layout.addWidget(button)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)


app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())