import sqlite3
from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QPushButton, QFileDialog, QMessageBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from datetime import datetime
import csv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt


class ReportsAnalyticsScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reports & Analytics")
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self.revenue_by_month_tab(), "Revenue by Month")
        tabs.addTab(self.unpaid_invoices_tab(), "Unpaid Invoices")
        tabs.addTab(self.appointments_by_species_tab(), "Appointments by Species")
        tabs.addTab(self.top_items_tab(), "Top Medications/Items")
        tabs.addTab(self.busiest_days_tab(), "Busiest Days/Times")
        tabs.addTab(self.appointments_by_vet_tab(), "Appointments by Vet")

        layout.addWidget(tabs)

    def revenue_by_month_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

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
            ax.bar(months, totals)
            ax.set_title("Revenue by Month")
            ax.set_ylabel("€")
            ax.set_xlabel("Month")
            ax.tick_params(axis='x', rotation=45)
        else:
            ax.text(0.5, 0.5, "No data", ha='center')

        layout.addWidget(canvas)

        # Add Export Button
        export_btn = QPushButton("Export Revenue to PDF")
        export_btn.clicked.connect(lambda: self.export_revenue_pdf(fig, data))
        layout.addWidget(export_btn)

        return widget

    def export_revenue_pdf(self, fig, data):
        if not data:
            QMessageBox.warning(self, "No Data", "No revenue data available to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "revenue_report.pdf", "PDF Files (*.pdf)")
        if not path:
            return

        # Save chart to image buffer
        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        chart_image = Image.open(buf)

        # Create PDF
        pdf = pdf_canvas.Canvas(path, pagesize=A4)
        width, height = A4
        pdf.setTitle("Revenue Report")

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, height - 50, "Pet Wellness Vets – Revenue Summary")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, height - 70, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        # Paste chart image
        img_path = "temp_chart.png"
        chart_image.save(img_path)
        pdf.drawImage(img_path, 50, height - 350, width=500, preserveAspectRatio=True)

        # Revenue table
        y = height - 370
        total_revenue = 0
        pdf.setFont("Helvetica", 10)
        for month, amount in data:
            pdf.drawString(60, y, f"{month}: €{amount:.2f}")
            y -= 15
            total_revenue += amount

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(60, y - 10, f"Total Revenue: €{total_revenue:.2f}")
        pdf.save()

        QMessageBox.information(self, "Success", f"Report saved to {path}")

    def unpaid_invoices_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.unpaid_table = QTableWidget()
        self.unpaid_table.setColumnCount(5)
        self.unpaid_table.setHorizontalHeaderLabels(["Invoice ID", "Appointment ID", "Patient", "Amount Due", "Created At"])
        self.unpaid_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

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

        self.unpaid_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(f"{val:.2f}" if isinstance(val, float) else str(val))
                self.unpaid_table.setItem(r_idx, c_idx, item)

        layout.addWidget(QLabel("Unpaid or Partially Paid Invoices"))
        layout.addWidget(self.unpaid_table)

        export_csv_btn = QPushButton("Export to CSV")
        export_csv_btn.clicked.connect(self.export_unpaid_csv)
        layout.addWidget(export_csv_btn)

        return widget

    def export_unpaid_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "unpaid_invoices.csv", "CSV Files (*.csv)")
        if not path:
            return

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Invoice ID", "Appointment ID", "Patient", "Amount Due", "Created At"])
            for r in range(self.unpaid_table.rowCount()):
                row = [self.unpaid_table.item(r, c).text() for c in range(self.unpaid_table.columnCount())]
                writer.writerow(row)

        QMessageBox.information(self, "Export Complete", f"Saved to {path}")

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

    def top_items_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT description, SUM(quantity) as total_sold
            FROM invoice_items
            GROUP BY description
            ORDER BY total_sold DESC
            LIMIT 10
        """)
        data = cursor.fetchall()
        conn.close()

        if data:
            items, counts = zip(*data)
            ax.barh(items, counts)
            ax.set_title("Top-Selling Medications/Items")
            ax.set_xlabel("Units Sold")
            ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, "No data", ha='center')

        layout.addWidget(canvas)
        return widget

    def busiest_days_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT strftime('%w', date_time) AS weekday, COUNT(*)
            FROM appointments
            GROUP BY weekday
        """)
        data = cursor.fetchall()
        conn.close()

        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        counts = [0] * 7
        for weekday, count in data:
            counts[int(weekday)] = count

        ax.bar(days, counts)
        ax.set_title("Appointments by Day of Week")
        ax.set_ylabel("Number of Appointments")
        ax.set_xticklabels(days, rotation=45)

        layout.addWidget(canvas)
        return widget

    def appointments_by_vet_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(6, 4))
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.veterinarian, COUNT(*)
            FROM appointments a
            WHERE a.veterinarian IS NOT NULL AND a.veterinarian != ''
            GROUP BY a.veterinarian
        """)
        data = cursor.fetchall()
        conn.close()

        if data:
            vets, counts = zip(*data)
            ax.bar(vets, counts)
            ax.set_title("Appointments by Veterinarian")
            ax.set_ylabel("Appointments")
            ax.set_xticklabels(vets, rotation=45)
        else:
            ax.text(0.5, 0.5, "No data", ha='center')

        layout.addWidget(canvas)
        return widget
