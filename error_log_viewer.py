from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, \
    QDateEdit, QHeaderView, QHBoxLayout, QMessageBox, QFileDialog
from PySide6.QtCore import QDate
import sqlite3
import csv

class ErrorLogViewer(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Error Log Viewer")
        self.setGeometry(200, 200, 800, 400)

        layout = QVBoxLayout()

        # **Date Filter**
        filter_layout = QHBoxLayout()
        self.start_date_filter = QDateEdit()  # ✅ Fix: Define it before load_logs()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDate(QDate.currentDate())

        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDate(QDate.currentDate())



        filter_layout.addWidget(self.start_date_filter)
        filter_layout.addWidget(self.end_date_filter)


        self.search_button = QPushButton("Filter Logs")
        self.search_button.clicked.connect(self.load_logs)
        filter_layout.addWidget(self.search_button)

        layout.addLayout(filter_layout)

        # **Error Log Table**
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["Timestamp", "Error Type", "Message"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.log_table)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self.export_logs_to_csv)
        layout.addWidget(self.export_button)

        self.setLayout(layout)

        # **Load logs after setting up UI elements**
        self.load_logs()  # ✅ Now safe to call, since self.start_date_filter is defined


    def load_logs(self):
        """Load logs from the error log file or database with filtering."""
        self.log_table.setRowCount(0)  # Clear table before loading new logs

        start_date = self.start_date_filter.date().toString("yyyy-MM-dd")
        end_date = self.end_date_filter.date().toString("yyyy-MM-dd")

        try:
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()

            query = "SELECT timestamp, error_message FROM error_logs WHERE timestamp BETWEEN ? AND ?"
            params = [start_date, end_date]


            query += " ORDER BY timestamp DESC"
            cursor.execute(query, params)
            logs = cursor.fetchall()
            conn.close()

            for row_index, row_data in enumerate(logs):
                self.log_table.insertRow(row_index)
                for col_index, col_data in enumerate(row_data):
                    self.log_table.setItem(row_index, col_index, QTableWidgetItem(str(col_data)))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load logs: {str(e)}")

    def export_logs_to_csv(self):
        """Export logs to a CSV file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Logs", "error_logs.csv", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, error_message FROM error_logs ORDER BY timestamp DESC")
            logs = cursor.fetchall()
            conn.close()

            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Error Message"])  # Headers

                for log in logs:
                    writer.writerow(log)

            QMessageBox.information(self, "Export Successful", f"Logs saved to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred while exporting: {str(e)}")

