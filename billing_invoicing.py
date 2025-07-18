import win32print
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFormLayout, QHeaderView, QFileDialog, QMessageBox, QSpinBox, QDialog, QDoubleSpinBox,
    QDateTimeEdit, QDateEdit
)
from PySide6.QtCore import QDateTime, QTimer, QDate, Signal
from PySide6 import QtGui
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrinterInfo
from PySide6.QtGui import QTextDocument
import inventory  # your existing inventory.py module
import tempfile
import os
import sqlite3
import csv
from logger import log_error  # Import the log_error function
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image
from reportlab.lib.units import mm
from PySide6.QtCore import QDateTime, QTimer, QDate, Signal, QSizeF, QMarginsF, QUrl
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

class PaymentHistoryDialog(QDialog):
    def __init__(self, invoice_id, parent=None):
        super().__init__()
        self.setWindowTitle("Payment History")
        self.invoice_id = invoice_id
        layout = QVBoxLayout()

        # Payment History Table
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(4)
        self.payment_table.setHorizontalHeaderLabels(["Payment Date", "Amount Paid", "Payment Method", "Notes"])
        self.payment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.payment_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.payment_table)

        self.load_payment_history()
        self.setLayout(layout)

    def load_payment_history(self):
        """Load payment history for the selected invoice."""
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT payment_date, amount_paid, payment_method, notes
            FROM payment_history
            WHERE invoice_id = ?
        ''', (self.invoice_id,))
        payments = cursor.fetchall()
        conn.close()

        self.payment_table.setRowCount(0)
        for row_index, row_data in enumerate(payments):
            self.payment_table.insertRow(row_index)
            for col_index, col_data in enumerate(row_data):
                self.payment_table.setItem(row_index, col_index, QTableWidgetItem(str(col_data)))

class AddPaymentDialog(QDialog):
    def __init__(self, invoice_id, remaining_balance):
        super().__init__()
        self.setWindowTitle("Add Payment")
        self.invoice_id = invoice_id
        self.remaining_balance = remaining_balance

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Payment Amount
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Enter Payment Amount")
        form_layout.addRow("Amount Paid:", self.amount_input)

        # Payment Method Dropdown
        self.payment_method_dropdown = QComboBox()
        self.payment_method_dropdown.addItems(["Cash", "Card", "Bank Transfer", "Online Payment", "Other"])
        form_layout.addRow("Payment Method:", self.payment_method_dropdown)

        # Notes
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional Notes")
        form_layout.addRow("Notes:", self.notes_input)

        layout.addLayout(form_layout)

        # Save Button
        save_button = QPushButton("Save Payment")
        save_button.clicked.connect(self.save_payment)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def save_payment(self):
        """Save the partial payment and update the invoice payment method."""
        try:
            amount_paid = float(self.amount_input.text().strip())
            if amount_paid <= 0:
                raise ValueError("Payment amount must be greater than zero.")
            if amount_paid > self.remaining_balance:
                raise ValueError("Payment amount exceeds remaining balance.")

            payment_method = self.payment_method_dropdown.currentText()
            notes = self.notes_input.text().strip()

            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()

            # Insert the payment into the payment_history table
            cursor.execute('''
                INSERT INTO payment_history (invoice_id, payment_date, amount_paid, payment_method, notes)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            ''', (self.invoice_id, amount_paid, payment_method, notes))

            # Update the payment_status and payment_method in the invoices table
            cursor.execute('''
                UPDATE invoices
                SET payment_status = CASE
                    WHEN (SELECT SUM(amount_paid) FROM payment_history WHERE invoice_id = ?) >= final_amount THEN 'Paid'
                    ELSE 'Partially Paid'
                END,
                payment_method = ?
                WHERE invoice_id = ?
            ''', (self.invoice_id, payment_method, self.invoice_id))

            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", "Payment added successfully.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")


class ItemizedBillingDialog(QDialog):
    """Dialog for Adding/Editing Invoice Items"""
    def __init__(self, invoice_id, item_id=None):
        super().__init__()
        self.setWindowTitle("Add/Edit Invoice Item")
        self.invoice_id = invoice_id
        self.item_id = item_id  # If None, we're adding a new item

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Service/Product Description
        self.description_input = QLineEdit()
        form_layout.addRow("Description:", self.description_input)

        # Quantity
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(1, 100)
        self.quantity_input.valueChanged.connect(self.calculate_total)
        form_layout.addRow("Quantity:", self.quantity_input)

        # Unit Price
        self.unit_price_input = QDoubleSpinBox()
        self.unit_price_input.setRange(0.01, 10000.00)
        self.unit_price_input.setDecimals(2)
        self.unit_price_input.valueChanged.connect(self.calculate_total)
        form_layout.addRow("Unit Price (€):", self.unit_price_input)

        # after unit_price_input…
        self.vat_pct_input = QSpinBox()
        self.vat_pct_input.setRange(0, 100)
        self.vat_pct_input.setSuffix(" %")
        self.vat_pct_input.valueChanged.connect(self.calculate_total)
        form_layout.addRow("VAT Rate (%):", self.vat_pct_input)

        # VAT Amount (Read-Only)
        self.vat_amount_label = QLineEdit("0.00")
        self.vat_amount_label.setReadOnly(True)
        form_layout.addRow("VAT Amount (€):", self.vat_amount_label)

        self.discount_pct_input = QSpinBox()
        self.discount_pct_input.setRange(0, 100)
        self.discount_pct_input.setSuffix(" %")
        self.discount_pct_input.valueChanged.connect(self.calculate_total)
        form_layout.addRow("Discount Rate (%):", self.discount_pct_input)

        # Discount Amount (Read-Only)
        self.discount_amount_label = QLineEdit("0.00")
        self.discount_amount_label.setReadOnly(True)
        form_layout.addRow("Discount Amount (€):", self.discount_amount_label)

        # Total Price (Read-Only)
        self.total_price_label = QLineEdit("0.00")
        self.total_price_label.setReadOnly(True)
        form_layout.addRow("Total Price (€):", self.total_price_label)

        layout.addLayout(form_layout)

        # Save Button
        save_button = QPushButton("Save Item")
        save_button.clicked.connect(self.save_item)
        layout.addWidget(save_button)

        self.setLayout(layout)

        if self.item_id:
            self.load_existing_item()

    def calculate_total(self):
        """Calculate total price based on quantity and unit price."""
        quantity = self.quantity_input.value()
        unit_price = self.unit_price_input.value()
        vat = (self.vat_pct_input.value() / 100.0) * (quantity * unit_price)
        self.vat_amount_label.setText(f"{vat:.2f}")
        discount = (self.discount_pct_input.value() / 100.0) * (quantity * unit_price)
        self.discount_amount_label.setText(f"{discount:.2f}")
        total = (quantity * unit_price) + vat - discount
        self.total_price_label.setText(f"{total:.2f}")

    def load_existing_item(self):
        """Load existing item details for editing."""
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT description, quantity, unit_price, vat_pct, vat_amount, discount_pct, 
            discount_amount, total_price FROM invoice_items WHERE item_id = ?
        ''', (self.item_id,))
        item = cursor.fetchone()
        conn.close()

        if item:
            self.description_input.setText(item[0])
            self.quantity_input.setValue(item[1])
            self.unit_price_input.setValue(item[2])
            self.vat_pct_input.setValue(item[3])
            self.vat_amount_label.setText(f"{item[4]:.2f}")
            self.discount_pct_input.setValue(item[5])
            self.discount_amount_label.setText(f"{item[6]:.2f}")
            self.calculate_total()

    def save_item(self):
        description = self.description_input.text().strip()
        if not description:
            QMessageBox.warning(self, "Input Error", "Description is required.")
            return

        quantity = self.quantity_input.value()
        unit_price = self.unit_price_input.value()
        vat_pct = self.vat_pct_input.value() / 100.0
        vat_amount = (self.vat_pct_input.value() / 100.0) * (quantity * unit_price)
        discount_pct = self.discount_pct_input.value() / 100.0
        discount_amount = (self.discount_pct_input.value() / 100.0) * (quantity * unit_price)
        total_price = (quantity * unit_price) + vat_amount - discount_amount

        try:
            print("Invoice ID when saving item:", self.invoice_id)  # Debug
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()

            if self.item_id:
                cursor.execute('''
                    UPDATE invoice_items SET description = ?, quantity = ?, unit_price = ?, vat_pct = ?, vat_amount = ?, 
                    discount_pct = ?, discount_amount = ?, total_price = ?
                    WHERE item_id = ?
                ''', (description, quantity, unit_price, vat_pct, vat_amount, discount_pct, discount_amount,
                      total_price, self.item_id))
            else:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, vat_pct, vat_amount, 
                    discount_pct,  discount_amount, total_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.invoice_id, description, quantity, unit_price, vat_pct, vat_amount,
                      discount_pct, discount_amount, total_price))

            conn.commit()
            conn.close()
            self.accept()  # ✅ Must be called to trigger reloading
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save item: {e}")


class InvoiceReminderDialog(QDialog):
    """Ask the user when & why to remind about this invoice."""
    def __init__(self, invoice_id, parent=None):
        super().__init__(parent)
        self.invoice_id = invoice_id
        self.setWindowTitle(f"Set Payment Reminder for Invoice #{invoice_id}")

        layout = QVBoxLayout()
        form = QFormLayout()

        # default to 24h from now
        dt = QDateTime.currentDateTime().addDays(1)
        self.dt_picker = QDateTimeEdit(dt)
        self.dt_picker.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_picker.setCalendarPopup(True)
        form.addRow("Reminder Time:", self.dt_picker)

        self.reason_input = QLineEdit(f"Invoice #{invoice_id} payment due")
        form.addRow("Reason:", self.reason_input)

        layout.addLayout(form)

        btns = QHBoxLayout()
        ok     = QPushButton("Save")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)

        layout.addLayout(btns)
        self.setLayout(layout)

    def get_values(self):
        """Return (ISO‐string, reason)."""
        ts = self.dt_picker.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        return ts, self.reason_input.text().strip()



class BillingInvoicingScreen(QWidget):
    invoiceSelected = Signal(int)  # emits invoice_id
    def __init__(self):
        super().__init__()

        # Initialize attributes
        self.selected_invoice_id = None
        self.invoices = []

        # Main layout
        layout = QVBoxLayout()

        # Filter and Search Layout
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Patient Name or Appointment ID...")
        self.search_input.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Open", "Paid"])
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.status_filter)

        # ─── date‐range filter ──────────────────────────────────────────────────────
        self.start_date = QDateEdit(QDate.currentDate().addMonths(-1))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.dateChanged.connect(self.apply_filters)

        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.dateChanged.connect(self.apply_filters)

        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)

        layout.addLayout(date_layout)
        # ───────────────────────────────────────────────────────────────────────────

        layout.addLayout(filter_layout)


        # Invoice Table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(10)
        self.invoice_table.setHorizontalHeaderLabels([
            "Invoice ID", "Appointment ID", "Patient Name", "Total Amount",
            "Final Amount", "Payment Status", "Payment Method", "Remaining Balance",
            "Created At", "Appointment Date"
        ])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.invoice_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.invoice_table.itemSelectionChanged.connect(self.load_selected_invoice)
        layout.addWidget(self.invoice_table)

        # Summary Section
        self.summary_section = QHBoxLayout()
        self.total_amount_label = QLabel("Total Amount: €0.00")
        self.remaining_balance_label = QLabel("Remaining Balance: €0.00")
        self.payment_count_label = QLabel("Payments: 0")
        self.item_count_label = QLabel("Items: 0")
        self.summary_section.addWidget(self.item_count_label)
        self.summary_section.addWidget(self.total_amount_label)
        self.summary_section.addWidget(self.remaining_balance_label)
        self.summary_section.addWidget(self.payment_count_label)

        layout.addLayout(self.summary_section)


        # Itemized Billing Table
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(6)
        self.item_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price", "VAT Amount", "Discount", "Total Price"])
        self.item_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.item_table.itemSelectionChanged.connect(self.load_selected_item)
        layout.addWidget(self.item_table)

        # Buttons for managing invoice items
        item_button_layout = QHBoxLayout()
        self.add_item_button = QPushButton("Add Item")
        self.add_item_button.setEnabled(False)
        self.add_item_button.clicked.connect(self.add_item)

        self.edit_item_button = QPushButton("Edit Item")
        self.edit_item_button.setEnabled(False)
        self.edit_item_button.clicked.connect(self.edit_item)

        self.delete_item_button = QPushButton("Delete Item")
        self.delete_item_button.setEnabled(False)
        self.delete_item_button.clicked.connect(self.delete_item)

        item_button_layout.addWidget(self.add_item_button)
        item_button_layout.addWidget(self.edit_item_button)
        item_button_layout.addWidget(self.delete_item_button)
        layout.addLayout(item_button_layout)

        # Form for invoice details
        form_layout = QFormLayout()

        readonly_style = "background-color: #f0f0f0; color: #555;"

        self.appointment_id_input = QLineEdit()
        self.appointment_id_input.setPlaceholderText("Enter Appointment ID")
        self.appointment_id_input.textChanged.connect(self.fetch_patient_details)
        form_layout.addRow("Appointment ID:", self.appointment_id_input)

        self.patient_name_label = QLineEdit()
        self.patient_name_label.setReadOnly(True)
        form_layout.addRow("Patient Name:", self.patient_name_label)

        self.total_amount_input = QLineEdit()
        self.total_amount_input.setReadOnly(True)  # Make total amount auto-calculated and non-editable
        self.total_amount_input.setStyleSheet(readonly_style)
        self.total_amount_input.setPlaceholderText("Enter Total Amount")
        form_layout.addRow("Total Amount:", self.total_amount_input)

        self.date_label = QLineEdit()
        self.date_label.setReadOnly(True)
        form_layout.addRow("Appointment Date:", self.date_label)

        # Tax and Discount
        self.tax_input = QSpinBox()
        self.tax_input.setRange(0, 100)  # Percentage
        self.tax_input.setSuffix(" %")
        self.tax_input.valueChanged.connect(self.calculate_final_amount)
        form_layout.addRow("Tax (%):", self.tax_input)

        self.discount_input = QSpinBox()
        self.discount_input.setRange(0, 100)  # Percentage
        self.discount_input.setSuffix(" %")
        self.discount_input.valueChanged.connect(self.calculate_final_amount)
        form_layout.addRow("Discount (%):", self.discount_input)

        # Final Amount
        self.final_amount_label = QLineEdit()
        self.final_amount_label.setReadOnly(True)
        self.final_amount_label.setStyleSheet(readonly_style)
        form_layout.addRow("Final Amount:", self.final_amount_label)

        # Remaining Balance
        self.remaining_balance_label = QLineEdit()
        self.remaining_balance_label.setReadOnly(True)
        self.remaining_balance_label.setStyleSheet(readonly_style)
        form_layout.addRow("Remaining Balance:", self.remaining_balance_label)

        self.payment_status_dropdown = QComboBox()
        self.payment_status_dropdown.addItems(["Unpaid", "Paid", "Partially Paid"])
        self.payment_status_dropdown.setEnabled(False)
        form_layout.addRow("Payment Status:", self.payment_status_dropdown)

        self.payment_method_dropdown = QComboBox()  # ✅ FIXED: Using the correct attribute
        self.payment_method_dropdown.addItems(["Cash", "Card", "Bank Transfer", "Other"])
        self.payment_method_dropdown.setEnabled(False)
        form_layout.addRow("Payment Method:", self.payment_method_dropdown)

        layout.addLayout(form_layout)

        # Buttons for actions
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create Invoice")
        self.create_button.clicked.connect(self.create_invoice)

        self.edit_button = QPushButton("Edit Invoice")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_invoice)

        self.finalize_button = QPushButton("Finalize Invoice")
        self.finalize_button.setEnabled(False)  # Disabled until an invoice is created
        self.finalize_button.clicked.connect(self.edit_invoice)  # Reuse existing logic
        button_layout.addWidget(self.finalize_button)

        self.view_payments_button = QPushButton("View Payments")
        self.view_payments_button.setEnabled(False)
        self.view_payments_button.clicked.connect(self.view_payment_history)

        self.add_payment_button = QPushButton("Add Payment")
        self.add_payment_button.setEnabled(False)
        self.add_payment_button.clicked.connect(self.add_payment)

        self.delete_payment_button = QPushButton("Delete Payment")
        self.delete_payment_button.setEnabled(False)
        self.delete_payment_button.clicked.connect(self.delete_payment)

        self.send_reminder_button = QPushButton("Send Reminder")
        self.send_reminder_button.setEnabled(False)
        self.send_reminder_button.clicked.connect(self.send_invoice_reminder)

        self.delete_button = QPushButton("Delete Invoice")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_invoice)

        self.print_button = QPushButton("Print Invoice")
        self.print_button.setEnabled(False)
        self.print_button.clicked.connect(self.print_invoice)

        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.view_payments_button)
        button_layout.addWidget(self.add_payment_button)
        button_layout.addWidget(self.delete_payment_button)
        button_layout.addWidget(self.send_reminder_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.print_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.load_invoices()

    def calculate_final_amount(self):
        """Calculate the final amount and remaining balance based on the invoice's appointment_id."""
        try:
            total = float(self.total_amount_input.text() or 0)
            tax = self.tax_input.value() / 100
            discount = self.discount_input.value() / 100
            final_amount = total + (total * tax) - (total * discount)
            self.final_amount_label.setText(f"{final_amount:.2f}")

            # Calculate remaining balance for this specific invoice
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COALESCE(SUM(amount_paid), 0)
                FROM payment_history
                WHERE invoice_id = ?
            ''', (self.selected_invoice_id,))
            total_paid = cursor.fetchone()[0]
            remaining_balance = final_amount - total_paid
            self.remaining_balance_label.setText(f"{remaining_balance:.2f}")
            conn.close()

            if remaining_balance <= 0:
                self.payment_status_dropdown.setCurrentText("Paid")
            elif remaining_balance < final_amount:
                self.payment_status_dropdown.setCurrentText("Partially Paid")
            else:
                self.payment_status_dropdown.setCurrentText("Unpaid")
        except ValueError:
            self.final_amount_label.setText("0.00")
            self.remaining_balance_label.setText("0.00")

    def view_payment_history(self):
        """Open the Payment History Dialog."""
        if not self.selected_invoice_id:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to view payment history.")
            return

        dialog = PaymentHistoryDialog(self.selected_invoice_id)
        dialog.exec()

    def add_payment(self):
        """Open the Add Payment Dialog and update balance for the specific invoice."""
        if not self.selected_invoice_id:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to add a payment.")
            return

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT final_amount - COALESCE((SELECT SUM(amount_paid) FROM payment_history WHERE invoice_id = ?), 0)
            FROM invoices WHERE invoice_id = ?
        ''', (self.selected_invoice_id, self.selected_invoice_id))
        remaining_balance = cursor.fetchone()[0]
        conn.close()

        if remaining_balance <= 0:
            QMessageBox.information(self, "No Balance", "This invoice is already fully paid.")
            return

        dialog = AddPaymentDialog(self.selected_invoice_id, remaining_balance)
        if dialog.exec():
            # 1) refresh the invoices grid
            self.load_invoices()
            # 2) re-populate the form fields (including payment_method)
            self.load_selected_invoice()

    def delete_payment(self):
        dialog = PaymentHistoryDialog(self.selected_invoice_id)
        # add a “Delete” button to the dialog:
        btn = QPushButton("Delete Selected")
        dialog.layout().addWidget(btn)
        btn.clicked.connect(lambda: self._confirm_delete(dialog))
        dialog.exec()

    def _confirm_delete(self, history_dialog):
        row = history_dialog.payment_table.currentRow()
        if row < 0:
            QMessageBox.warning(history_dialog, "No Payment", "Select one to delete.")
            return
        # assume payment_id is stored in hidden column 0; otherwise fetch via date+amount
        payment_date = history_dialog.payment_table.item(row, 0).text()
        amount = history_dialog.payment_table.item(row, 1).text()
        # delete by matching invoice_id+timestamp+amount
        conn = sqlite3.connect("vet_management.db")
        cur = conn.cursor()
        cur.execute("""
           DELETE FROM payment_history
            WHERE invoice_id=? AND payment_date=? AND amount_paid=?
           """,
                    (self.selected_invoice_id, payment_date, amount))
        conn.commit()
        conn.close()

        history_dialog.load_payment_history()

        # ← NEW: recalc & persist your invoice status/balance
        final = float(self.final_amount_label.text() or 0)
        self.update_payment_status_and_balance(self.selected_invoice_id, final)

        # refresh balances
        self.load_invoices()
        self.load_selected_invoice()

    def send_invoice_reminder(self):
        """Open a dialog to pick date+reason, then insert into reminders."""
        if not self.selected_invoice_id:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice first.")
            return

        dlg = InvoiceReminderDialog(self.selected_invoice_id, self)
        if dlg.exec() != QDialog.Accepted:
            return

        rem_time, reason = dlg.get_values()
        appt_id = int(self.appointment_id_input.text())

        try:
            conn = sqlite3.connect("vet_management.db")
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO reminders (appointment_id, reminder_time, reminder_status, reminder_reason)
                VALUES (?, ?, 'Pending', ?)
            """, (appt_id, rem_time, reason))
            conn.commit()
        finally:
            conn.close()

        QMessageBox.information(
            self, "Reminder Scheduled",
            f"Payment reminder set for {rem_time}.\nReason: {reason}"
        )


    def load_invoices(self):
        """Load all invoices into the table with appointment-specific data."""
        try:
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.invoice_id, i.appointment_id, (SELECT name FROM patients WHERE patient_id = a.patient_id),
                       i.total_amount, i.final_amount, i.payment_status, i.payment_method,
                       (i.final_amount - COALESCE((SELECT SUM(amount_paid) FROM payment_history WHERE invoice_id = i.invoice_id), 0)),
                       i.created_at, a.date_time
                FROM invoices i
                JOIN appointments a ON i.appointment_id = a.appointment_id
            ''')
            self.invoices = cursor.fetchall()
            conn.close()
            self.apply_filters()

        except Exception as e:
            log_error(f"Database Error in load_invoices: {str(e)}")
            QMessageBox.critical(self, "Database Error", f"An unexpected error occurred: {str(e)}")

    def apply_filters(self):
        """Filter and display invoices based on search text, status, AND date‐range."""
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()
        start_date = self.start_date.date()
        end_date = self.end_date.date()

        filtered_invoices = []
        total_amount = 0
        remaining_balance = 0
        payment_count = 0

        for invoice in self.invoices:
            invoice_id, appointment_id, patient_name, total_amt, final_amt, status,_, balance, created_at, appointment_date = invoice
            created_day = QDate.fromString(created_at.split(" ")[0], "yyyy-MM-dd")
            if created_day < start_date or created_day > end_date:
                continue
            if search_text and search_text not in str(appointment_id).lower() and search_text not in patient_name.lower():
                continue
            if status_filter == "Open" and status == "Paid":
                continue
            if status_filter == "Paid" and status != "Paid":
                continue
            filtered_invoices.append(invoice)
            total_amount += final_amt
            remaining_balance += balance
            if status != "Unpaid":
                payment_count += 1

        # Update table
        self.invoice_table.setRowCount(0)
        for row_data in filtered_invoices:
            row_index = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row_index)

            for col_index, col_data in enumerate(row_data):
                # if this is a money column (Total Amount, Final Amount, Remaining Balance)
                if col_index in (3, 4, 7):
                    try:
                        # format to exactly two decimals
                        display = f"{float(col_data):.2f}"
                    except (ValueError, TypeError):
                        display = str(col_data)
                else:
                    display = str(col_data)
                item = QTableWidgetItem(display)

                # Apply color-coding to the "Payment Status" column (index 5)
                if col_index == 5:
                    status = str(col_data).strip().lower()
                    if status == "paid":
                        item.setBackground(QtGui.QColor("#d4edda"))  # Light green
                    elif status == "partially paid":
                        item.setBackground(QtGui.QColor("#fff3cd"))  # Light yellow
                    elif status == "unpaid":
                        item.setBackground(QtGui.QColor("#f8d7da"))  # Light red
                    else:
                        item.setBackground(QtGui.QColor("white"))  # fallback

                self.invoice_table.setItem(row_index, col_index, item)

        # Update summary
        self.total_amount_label.setText(f"Total Amount: {total_amount:.2f}")
        self.remaining_balance_label.setText(f"Remaining Balance: {remaining_balance:.2f}")
        self.payment_count_label.setText(f"Payments: {payment_count}")

    def load_selected_invoice(self):
        """Load selected invoice details into the form from the database."""
        # 1) figure out which row is selected in the QTableWidget
        sel = self.invoice_table.currentRow()
        if sel < 0:
            return

        # 2) grab the invoice_id out of the first column of that row
        self.selected_invoice_id = int(self.invoice_table.item(sel, 0).text())

        # 3) fetch the *canonical* invoice row
        conn = sqlite3.connect("vet_management.db")
        cur  = conn.cursor()
        cur.execute("""
            SELECT appointment_id,
                   total_amount,
                   tax,
                   discount,
                   final_amount,
                   remaining_balance,
                   payment_status,
                   payment_method
            FROM invoices
            WHERE invoice_id = ?
        """, (self.selected_invoice_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            QMessageBox.critical(self, "Error",
                                 "Could not load invoice details from the database.")
            return

        (appt_id,
         total_amt,
         tax_pct,
         disc_pct,
         final_amt,
         rem_bal,
         status,
         method) = row

        # 4) seed the form fields with exactly what’s in the DB
        self.appointment_id_input.setText(str(appt_id))
        self.total_amount_input.setText(f"{total_amt:.2f}")
        self.tax_input.setValue(int(tax_pct))
        self.discount_input.setValue(int(disc_pct))
        self.final_amount_label.setText(f"{final_amt:.2f}")
        self.remaining_balance_label.setText(f"{rem_bal:.2f}")
        self.payment_status_dropdown.setCurrentText(status)
        self.payment_method_dropdown.setCurrentText(method)

        # 5) (optional) fetch & set the patient name + appointment date
        self.fetch_patient_details()

        # 6) re-enable your buttons
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.view_payments_button.setEnabled(True)
        self.add_payment_button.setEnabled(True)
        self.delete_payment_button.setEnabled(True)
        self.send_reminder_button.setEnabled(True)
        self.add_item_button.setEnabled(True)
        self.print_button.setEnabled(True)

        # 7) now reload item rows (which will recalc totals if you call calculate_final_amount())
        self.load_invoice_items()

        # if you have a pointer to your notifications screen:
        self.invoiceSelected.emit(self.selected_invoice_id)

    def load_invoice_items(self):
        """Load itemized billing for selected invoice and update total amount."""
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT description, quantity, unit_price, vat_amount, discount_amount, total_price FROM invoice_items WHERE invoice_id = ?
        ''', (self.selected_invoice_id,))
        items = cursor.fetchall()
        conn.close()

        self.item_table.setRowCount(0)
        item_total = 0.0
        for row_data in items:
            self.item_table.insertRow(self.item_table.rowCount())
            for col_index, col_data in enumerate(row_data):
                self.item_table.setItem(self.item_table.rowCount() - 1, col_index, QTableWidgetItem(str(col_data)))
            item_total += float(row_data[3])

        self.calculate_totals_from_items()  # More maintainable
        self.item_count_label.setText(f"Items: {len(items)}")  # Show item count
        self.calculate_final_amount()  # Recalculate with updated total

    def load_selected_item(self):
        """Enable edit and delete buttons when an item is selected."""
        selected_row = self.item_table.currentRow()
        if selected_row < 0:
            self.edit_item_button.setEnabled(False)
            self.delete_item_button.setEnabled(False)
            return

        self.edit_item_button.setEnabled(True)
        self.delete_item_button.setEnabled(True)

    def add_item(self):
        dialog = ItemizedBillingDialog(self.selected_invoice_id)
        if dialog.exec():
            print("Dialog accepted, reloading items")  # Debug
            self.load_invoice_items()

    def edit_item(self):
        """Edit selected invoice item."""
        selected_row = self.item_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "No Item Selected", "Please select an item to edit.")
            return

        description = self.item_table.item(selected_row, 0).text()

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT item_id FROM invoice_items WHERE description = ? AND invoice_id = ?
        ''', (description, self.selected_invoice_id))
        item_id = cursor.fetchone()
        conn.close()

        if item_id:
            dialog = ItemizedBillingDialog(self.selected_invoice_id, item_id[0])
            if dialog.exec():
                self.load_invoice_items()  # Reload items after editing
        else:
            QMessageBox.warning(self, "Error", "Could not find the selected item in the database.")

    def delete_item(self):
        """Delete selected invoice item."""
        selected_row = self.item_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "No Item Selected", "Please select an item to delete.")
            return

        reply = QMessageBox.question(self, "Delete Confirmation",
                                     "Are you sure you want to delete this item?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        description = self.item_table.item(selected_row, 0).text()

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM invoice_items WHERE description = ? AND invoice_id = ?
        ''', (description, self.selected_invoice_id))
        conn.commit()
        conn.close()

        self.load_invoice_items()  # Reload items after deletion

    def fetch_patient_details(self):
        """Fetch patient details based on appointment ID."""
        appointment_id = self.appointment_id_input.text()
        if not appointment_id:
            self.patient_name_label.clear()
            self.date_label.clear()
            return

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.name, a.date_time
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.appointment_id = ?
        ''', (appointment_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            patient_name, appointment_date = result
            self.patient_name_label.setText(patient_name)
            self.date_label.setText(appointment_date)
            self.add_item_button.setEnabled(True)
        else:
            self.patient_name_label.clear()
            self.date_label.clear()
            self.add_item_button.setEnabled(False)

    def create_invoice(self):
        """Stage 1: Create a draft invoice entry so items can be added, then finalize it."""
        try:
            appointment_id = self.appointment_id_input.text().strip()
            if not appointment_id:
                QMessageBox.warning(self, "Input Error", "Appointment ID is required.")
                return

            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()

            # Check for duplicate invoice
            cursor.execute("SELECT invoice_id FROM invoices WHERE appointment_id = ?", (appointment_id,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Duplicate Invoice", "An invoice already exists for this appointment.")
                conn.close()
                return

            # Insert draft invoice with zeroed values
            cursor.execute('''
                INSERT INTO invoices (appointment_id, total_amount, tax, discount, final_amount, payment_status, payment_method)
                VALUES (?, 0, 0, 0, 0, 'Unpaid', ?)
            ''', (appointment_id, self.payment_method_dropdown.currentText()))

            # …after you insert the draft invoice and get its ID…
            self.selected_invoice_id = cursor.lastrowid

            conn.commit()
            conn.close()

            QMessageBox.information(self, "Invoice Created", "Draft invoice created. You can now add items.")
            self.add_item_button.setEnabled(True)
            self.finalize_button.setEnabled(True)

            # load header fields…
            self.load_invoice_details(appointment_id)
            # **and then immediately clear out any items/totals from the old invoice:**
            self.load_invoice_items()


        except Exception as e:
            log_error(f"Error in create_invoice: {str(e)}")
            QMessageBox.critical(self, "Error", "Failed to create draft invoice.")

    def edit_invoice(self):
        """Edit an existing invoice and update all invoice_items including VAT‐ & discount‐fractions."""
        if not self.selected_invoice_id:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to edit.")
            return

        appointment_id = self.appointment_id_input.text().strip()
        if not appointment_id:
            QMessageBox.warning(self, "Input Error", "Appointment ID is required.")
            return

        try:
            # 1) Recalculate totals from the UI
            total_amount, final_amount = self.calculate_totals_from_items()
            tax = self.tax_input.value()
            discount = self.discount_input.value()
            payment_status = self.payment_status_dropdown.currentText()
            payment_method = self.payment_method_dropdown.currentText()

            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()

            # 2) Update the invoices table
            cursor.execute(
                """
                UPDATE invoices
                   SET appointment_id = ?, total_amount = ?, tax = ?, discount = ?,
                       final_amount = ?, payment_status = ?, payment_method = ?
                 WHERE invoice_id = ?
                """,
                (
                    appointment_id, total_amount, tax, discount,
                    final_amount, payment_status, payment_method,
                    self.selected_invoice_id
                )
            )

            # 3) Wipe out old items
            cursor.execute(
                "DELETE FROM invoice_items WHERE invoice_id = ?",
                (self.selected_invoice_id,)
            )

            # 4) Re‐insert each row, this time including vat_pct, discount_pct & vat_flag
            for row in range(self.item_table.rowCount()):
                desc = self.item_table.item(row, 0).text().strip()
                qty = int(self.item_table.item(row, 1).text())
                unit_price = float(self.item_table.item(row, 2).text())
                vat_amount = float(self.item_table.item(row, 3).text())
                discount_amount = float(self.item_table.item(row, 4).text())
                total_price = float(self.item_table.item(row, 5).text())

                # recompute fractions
                base = qty * unit_price if qty and unit_price else 1
                vat_frac = vat_amount / base
                discount_frac = discount_amount / base

                # integer % for storage
                vat_pct = vat_frac * 100
                disc_pct = discount_frac * 100

                # default flags if missing
                rate = int(round(vat_pct))
                if rate not in (5, 19):
                    # fall back: small-amount => 5%, large => 19%
                    rate = 5 if vat_amount < 1 else 19
                flag = "B" if rate == 5 else "C" if rate == 19 else ""

                cursor.execute(
                    """
                    INSERT INTO invoice_items
                      (invoice_id,
                       description,
                       quantity,
                       unit_price,
                       vat_pct,
                       vat_amount,
                       discount_pct,
                       discount_amount,
                       total_price,
                       vat_flag)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        self.selected_invoice_id,
                        desc,
                        qty,
                        unit_price,
                        vat_frac,  # store as fraction 0.19 or 0.05
                        vat_amount,
                        discount_frac,  # store as fraction, too
                        discount_amount,
                        total_price,
                        flag
                    )
                )

            # ── AFTER you’ve deleted/inserted all your invoice_items but BEFORE COMMIT ──

            # AUTO-STOCK DEDUCTION (same sqlite3 connection)
            for row in range(self.item_table.rowCount()):
                # we assume your "Description" column exactly matches an inventory item's name
                desc = self.item_table.item(row, 0).text().strip()
                qty = int(self.item_table.item(row, 1).text())

                # look up the SKU
                cursor.execute("SELECT item_id FROM items WHERE name = ?", (desc,))
                res = cursor.fetchone()
                if not res:
                    continue
                item_id = res[0]

                # insert one stock_movement reducing on-hand
                ts = datetime.now().isoformat(" ", "seconds")
                cursor.execute("""
                    INSERT INTO stock_movements
                      (item_id, change_qty, reason, timestamp)
                    VALUES (?,       ?,          ?,      ?)
                """, (
                    item_id,
                    -qty,
                    f"Sold/Dispensed via Invoice #{self.selected_invoice_id}",
                    ts
                ))


            # ── NOW commit everything in one go ──
            conn.commit()


            # 5) Finally, update invoice-level balance & status
            self.update_payment_status_and_balance(self.selected_invoice_id, final_amount)
            QMessageBox.information(self, "Success", "Invoice updated successfully.")



            self.finalize_button.setEnabled(False)

            # 6) Refresh the UI
            self.load_invoices()
            self.clear_inputs()
            self.clear_invoice_form()
            self.calculate_final_amount()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {e}")
            log_error(f"Finalize Invoice #{self.selected_invoice_id} failed: {e}")

        finally:
            conn.close()

    def delete_invoice(self):
        """Delete the selected invoice."""
        if not hasattr(self, 'selected_invoice_id'):
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to delete.")
            return

        reply = QMessageBox.question(self, "Delete Confirmation", "Are you sure you want to delete this invoice?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices WHERE invoice_id = ?", (self.selected_invoice_id,))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Invoice deleted successfully.")
        self.load_invoices()
        self.clear_inputs()
        self.clear_invoice_form()  # ✅ Clear the form after editing an invoice

    # In billing_invoicing.py, inside your BillingInvoicingScreen class:

    def print_invoice(self):
        """Fetch invoice data, then offer Save-PDF or Print (with logo, header, items, VAT‐breakdown, signatures)."""
        # 1) Ensure an invoice is selected
        if not getattr(self, "selected_invoice_id", None):
            QMessageBox.warning(self, "No Invoice", "Please select an invoice first.")
            return
        inv_id = self.selected_invoice_id

        # 2) Fetch owner & pet
        conn = sqlite3.connect("vet_management.db")
        cur = conn.cursor()
        cur.execute("""
          SELECT p.owner_name, p.owner_contact, p.name
            FROM appointments a
            JOIN patients   p ON a.patient_id = p.patient_id
           WHERE a.appointment_id = ?
        """, (int(self.appointment_id_input.text() or 0),))
        owner_name, owner_contact, pet_name = cur.fetchone() or ("", "", "")
        conn.close()

        # 3) Fetch invoice items (with VAT & discounts)
        conn = sqlite3.connect("vet_management.db")
        cur = conn.cursor()
        cur.execute("""
          SELECT description, quantity, unit_price,
                 discount_pct, discount_amount,
                 total_price,
                 vat_pct, vat_amount, vat_flag
            FROM invoice_items
           WHERE invoice_id = ?
        """, (inv_id,))
        raw_items = cur.fetchall()
        conn.close()

        items = [
            {
                "desc": desc, "qty": qty,
                "unit": unit, "disc_amt": d_amt,
                "total": total, "vat_amt": vat_amt
            }
            for desc, qty, unit, _, d_amt, total, _, vat_amt, _ in raw_items
        ]

        # 4) Build VAT breakdown by rate
        grouping = {}
        for desc, qty, unit, d_pct, d_amt, total, v_pct, v_amt, v_flag in raw_items:
            net = total - v_amt
            grp = grouping.setdefault(v_pct, {"net": 0.0, "vat_amount": 0.0, "flag": v_flag})
            grp["net"] += net
            grp["vat_amount"] += v_amt

        vat_breakdown = [
            {"vat_pct": rate, "net": data["net"], "vat_amount": data["vat_amount"], "flag": data["flag"]}
            for rate, data in grouping.items()
        ]

        # *** HERE: define total_vat ***
        total_vat = sum(b["vat_amount"] for b in vat_breakdown)

        # 5) Fetch invoice‐level discount & final total
        conn = sqlite3.connect("vet_management.db")
        cur = conn.cursor()
        cur.execute("SELECT discount, final_amount FROM invoices WHERE invoice_id = ?", (inv_id,))
        disc_pct, final_total = cur.fetchone() or (0.0, sum(it["total"] for it in items))
        conn.close()
        subtotal = sum(it["total"] for it in items)

        # 6) Ask user Save-PDF or Print
        msg = QMessageBox(self)
        msg.setWindowTitle("Invoice Output")
        msg.setText("Save as PDF or send directly to printer?")
        pdf_btn = msg.addButton("Save as PDF", QMessageBox.AcceptRole)
        print_btn = msg.addButton("Print to Printer", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()

        # — PDF branch (unchanged) —
        if clicked == pdf_btn:
            default_fn = f"Invoice_{inv_id}_{owner_name.replace(' ', '')}_{datetime.now():%Y%m%d}.pdf"
            path, _ = QFileDialog.getSaveFileName(self, "Save Invoice as PDF", default_fn, "PDF Files (*.pdf)")
            if path:
                try:
                    self.generate_pdf(
                        path=path,
                        inv_id=inv_id,
                        created_date=datetime.now().strftime("%d-%b-%Y"),
                        created_time=datetime.now().strftime("%H:%M"),
                        customer=owner_name,
                        pet_name=pet_name,
                        items=items,
                        subtotal=subtotal,
                        discount_pct=disc_pct,
                        discount_amount=subtotal * (disc_pct / 100.0),
                        final_total=final_total,
                        vat_breakdown=vat_breakdown
                    )
                    QMessageBox.information(self, "Saved", f"Invoice saved to:\n{path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not create PDF:\n{e}")
            return

        # — Print branch —
        if clicked is print_btn:
            # 1) Create a temp PDF at 80 mm width
            tmp_path = os.path.join(
                tempfile.gettempdir(),
                f"Invoice_{inv_id}_{owner_name.replace(' ', '')}.pdf"
            )
            self.generate_pdf(
                path=tmp_path,
                inv_id=inv_id,
                created_date=datetime.now().strftime("%d-%b-%Y"),
                created_time=datetime.now().strftime("%H:%M"),
                customer=owner_name,
                pet_name=pet_name,
                items=items,
                subtotal=subtotal,
                discount_pct=disc_pct,
                discount_amount=subtotal * (disc_pct / 100.0),
                final_total=final_total,
                vat_breakdown=vat_breakdown
            )

            # 2) Find your thermal printer
            thermal_name = None
            for pi in QPrinterInfo.availablePrinters():
                n = pi.printerName().lower()
                if "thermal" in n or "epson" in n:
                    thermal_name = pi.printerName()
                    break

            if not thermal_name:
                QMessageBox.warning(
                    self, "Printer Not Found",
                    "Could not find your thermal printer. "
                    "Make sure its driver is installed and its name contains “Thermal” or “Epson”."
                )
                return

            # 3) Temporarily switch default → print → restore
            original = win32print.GetDefaultPrinter()
            try:
                win32print.SetDefaultPrinter(thermal_name)
                os.startfile(tmp_path, "print")
            finally:
                win32print.SetDefaultPrinter(original)

    def generate_pdf(self,
                     path,
                     inv_id, created_date, created_time,
                     customer, pet_name, items,
                     subtotal, discount_pct, discount_amount,
                     final_total, vat_breakdown
                     ):
        """
        Build an 80 mm thermal-receipt PDF, auto-trimmed height,
        Courier font, full items + VAT breakdown + signatures.
        """
        width, margin = 80*mm, 5*mm
        cw = width - 2*margin

        styles = getSampleStyleSheet()
        styles["Normal"].fontName = "Courier"; styles["Normal"].fontSize = 6
        styles["Title"].fontName  = "Courier-Bold"; styles["Title"].fontSize  = 9

        elems = []

        # Logo (optional)
        logo_fp = os.path.join(os.path.dirname(__file__), "pet_wellness_logo.png")
        if os.path.exists(logo_fp):
            img = Image(logo_fp, width=cw*0.6, height=cw*0.3)
            img.hAlign="CENTER"; elems.append(img); elems.append(Spacer(1,3*mm))

        # Clinic header
        elems.append(Paragraph("PET WELLNESS VETS", styles["Title"]))
        elems.append(Paragraph("Kyriakou Adamou no.2, Shop 2&3, 8220", styles["Normal"]))
        elems.append(Paragraph("Tel: 99941186   Email: contact@petwellnessvets.com", styles["Normal"]))
        elems.append(Spacer(1,5*mm))

        # Invoice meta
        meta = [
          ["Inv#:", str(inv_id), "Date:", created_date],
          ["Time:", created_time, "Customer:", customer],
          ["Pet:", pet_name, "", ""]
        ]
        colw = [cw*0.2, cw*0.3, cw*0.2, cw*0.3]
        tbl = Table(meta, colWidths=colw)
        tbl.setStyle(TableStyle([
          ("FONTSIZE",(0,0),(-1,-1),7),
          ("BOTTOMPADDING",(0,0),(-1,-1),2),
        ]))
        elems.append(tbl); elems.append(Spacer(1,3*mm))

        # Items + per-row VAT
        data = [["Desc","Qty","Unit","Disc","Total","VAT"]]
        for it in items:
            data.append([
              it["desc"],
              str(it["qty"]),
              f"{it['unit']:.2f}",
              f"{it['disc_amt']:.2f}",
              f"{it['total']:.2f}",
              f"{it['vat_amt']:.2f}"
            ])
        colw = [cw*0.40, cw*0.1, cw*0.15, cw*0.1, cw*0.15, cw*0.1]
        itbl = Table(data, colWidths=colw)
        itbl.setStyle(TableStyle([
          ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
          ("GRID",(0,0),(-1,-1),0.3,colors.black),
          ("FONTSIZE",(0,0),(-1,-1),7),
          ("ALIGN",(1,1),(-1,-1),"RIGHT"),
        ]))
        elems.append(itbl); elems.append(Spacer(1,3*mm))

        # Summary
        summary = [
          ["Subtotal:",            f"€{subtotal:.2f}"],
          [f"Discount ({discount_pct:.0f}%):", f"–€{discount_amount:.2f}"],
          ["Total:",               f"€{final_total:.2f}"]
        ]
        colw = [cw*0.7, cw*0.3]
        stbl = Table(summary, colWidths=colw, hAlign="RIGHT")
        stbl.setStyle(TableStyle([
          ("FONTSIZE",(0,0),(-1,-1),7),
          ("ALIGN",(1,0),(-1,-1),"RIGHT"),
          ("BOTTOMPADDING",(0,0),(-1,-1),2),
        ]))
        elems.append(stbl); elems.append(Spacer(1,3*mm))

        # VAT breakdown by rate
        vat_data = [["Net", "VAT%", "VAT", "Flag"]]
        for row in vat_breakdown:
            vat_data.append([
                f"{row['net']:.2f}",
                f"{row['vat_pct']}%",
                f"{row['vat_amount']:.2f}",
                row["flag"]
            ])
        total_vat = sum(r["vat_amount"] for r in vat_breakdown)
        vat_data.append(["", "", "Total VAT", f"€{total_vat:.2f}"])

        colw = [cw * 0.4, cw * 0.2, cw * 0.2, cw * 0.2]
        vtbl = Table(vat_data, colWidths=colw)
        vtbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ]))
        elems.append(vtbl)
        elems.append(Spacer(1, 5 * mm))

        # Signatures
        sig = [["Doctor:","Issued By:","Received By:"],["____","____","____"]]
        s_tbl = Table(sig, colWidths=[cw/3]*3)
        s_tbl.setStyle(TableStyle([
          ("FONTSIZE",(0,0),(-1,-1),7),
          ("BOTTOMPADDING",(0,0),(2,0),4),
        ]))
        elems.append(s_tbl)

        # Auto-trim height
        total_h = margin*2
        for f in elems:
            _, h = f.wrap(cw, A4[1]); total_h += h

        doc = SimpleDocTemplate(path,
            pagesize=(width, total_h),
            leftMargin=margin, rightMargin=margin,
            topMargin=margin, bottomMargin=margin)
        doc.build(elems)


    def clear_invoice_form(self):
        """Clear all input fields and reset the form."""
        self.appointment_id_input.clear()
        self.patient_name_label.clear()
        self.total_amount_input.clear()
        self.tax_input.setValue(0)
        self.discount_input.setValue(0)
        self.final_amount_label.clear()
        self.remaining_balance_label.clear()
        self.payment_status_dropdown.setCurrentIndex(0)
        self.payment_method_dropdown.setCurrentIndex(0)

        # Clear the item table
        self.item_table.setRowCount(0)

        # Disable edit and delete buttons
        self.edit_button.setEnabled(False)
        self.finalize_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.view_payments_button.setEnabled(False)
        self.add_payment_button.setEnabled(False)
        self.print_button.setEnabled(False)

    def load_invoice_details(self, appointment_id):
        """Load appointment details into the invoice form."""
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.appointment_id, p.name, a.date_time
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.appointment_id = ?
        ''', (appointment_id,))
        appointment = cursor.fetchone()
        conn.close()

        if appointment:
            self.appointment_id_input.setText(str(appointment[0]))
            self.patient_name_label.setText(appointment[1])
            self.date_label.setText(appointment[2])  # Set the date in the date_label
        else:
            QMessageBox.warning(self, "Error", "Could not load appointment details.")

    def calculate_totals_from_items(self):
        """Recalculate total and final amounts from invoice items."""
        item_total = 0.0
        for row in range(self.item_table.rowCount()):
            try:
                total_price = float(self.item_table.item(row, 5).text())
                item_total += total_price
            except (ValueError, AttributeError):
                continue

        self.total_amount_input.setText(f"{item_total:.2f}")
        tax = self.tax_input.value() / 100
        discount = self.discount_input.value() / 100
        final = item_total + (item_total * tax) - (item_total * discount)
        self.final_amount_label.setText(f"{final:.2f}")

        return item_total, final

    def update_payment_status_and_balance(self, invoice_id, final_amount):
        """Recalculate payment totals and update the invoice status."""
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(SUM(amount_paid), 0) FROM payment_history WHERE invoice_id = ?', (invoice_id,))
        total_paid = cursor.fetchone()[0]
        remaining_balance = final_amount - total_paid

        payment_status = (
            "Paid" if remaining_balance <= 0 else
            "Partially Paid" if remaining_balance < final_amount else
            "Unpaid"
        )

        cursor.execute('''
            UPDATE invoices SET remaining_balance = ?, payment_status = ? WHERE invoice_id = ?
        ''', (remaining_balance, payment_status, invoice_id))

        conn.commit()
        conn.close()

    def export_to_csv(self):
        """Export invoice data to a CSV file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "invoices.csv", "CSV Files (*.csv)")
        if not file_path:
            return

        row_count = self.invoice_table.rowCount()
        column_count = self.invoice_table.columnCount()

        if row_count == 0:
            QMessageBox.warning(self, "No Data", "There are no invoices to export.")
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                # Write headers
                headers = [self.invoice_table.horizontalHeaderItem(col).text() for col in range(column_count)]
                writer.writerow(headers)

                # Write rows
                for row in range(row_count):
                    row_data = [self.invoice_table.item(row, col).text() for col in range(column_count)]
                    writer.writerow(row_data)

            QMessageBox.information(self, "Export Successful", f"Invoices exported to {file_path}.")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred while exporting: {str(e)}")



    def clear_inputs(self):
        """Clear all input fields."""
        self.appointment_id_input.clear()
        self.patient_name_label.clear()
        self.total_amount_input.clear()
        self.tax_input.setValue(0)
        self.discount_input.setValue(0)
        self.final_amount_label.clear()
        self.payment_status_dropdown.setCurrentIndex(0)
        self.payment_method_dropdown.clear()

        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.finalize_button.setEnabled(False)
