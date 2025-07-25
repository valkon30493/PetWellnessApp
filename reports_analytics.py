import sqlite3
from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from datetime import datetime

class ReportsAnalyticsScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reports & Analytics")
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self.revenue_by_month_tab(), "Revenue by Month")
        tabs.addTab(self.unpaid_invoices_tab(), "Unpaid Invoices")
        tabs.addTab(self.appointments_by_species_tab(), "Appointments by Species")

        layout.addWidget(tabs)

    def revenue_by_month_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        # Query revenue grouped by month
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT strftime('%Y-%m', created_at) AS month, SUM(final_amount)
            FROM invoices
            GROUP BY month
            ORDER BY month
        """)
        data = cursor.fetchall()
        conn.close()

        if data:
            months, totals = zip(*data)
            ax.bar(months, totals, label="Revenue")
            ax.set_title("Revenue by Month")
            ax.set_ylabel("€")
            ax.set_xlabel("Month")
            ax.tick_params(axis='x', rotation=45)
        else:
            ax.text(0.5, 0.5, "No data", ha='center')

        layout.addWidget(canvas)
        return widget

    def unpaid_invoices_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        table = QTableWidget()
        layout.addWidget(QLabel("Unpaid or Partially Paid Invoices"))
        layout.addWidget(table)

        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Invoice ID", "Appointment ID", "Patient", "Amount Due", "Created At"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.invoice_id, i.appointment_id, p.name,
                   (i.final_amount - IFNULL((SELECT SUM(amount_paid) FROM payment_history WHERE invoice_id = i.invoice_id), 0)) AS due,
                   i.created_at
            FROM invoices i
            JOIN appointments a ON i.appointment_id = a.appointment_id
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE i.payment_status != 'Paid'
        """)
        rows = cursor.fetchall()
        conn.close()

        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(f"{val:.2f}" if isinstance(val, float) else str(val))
                table.setItem(r_idx, c_idx, item)

        return widget

    def appointments_by_species_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.species, COUNT(*)
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            GROUP BY p.species
        """)
        data = cursor.fetchall()
        conn.close()

        if data:
            species, counts = zip(*data)
            ax.pie(counts, labels=species, autopct='%1.1f%%', startangle=140)
            ax.set_title("Appointments by Species")
        else:
            ax.text(0.5, 0.5, "No data", ha='center')

        layout.addWidget(canvas)
        return widget
