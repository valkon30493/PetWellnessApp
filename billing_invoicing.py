from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QComboBox, QFormLayout, QHeaderView, QFileDialog, QMessageBox, QSpinBox, QDialog, QDoubleSpinBox
)
import sqlite3
import csv
from logger import log_error  # Import the log_error function


class PaymentHistoryDialog(QDialog):
    def __init__(self, invoice_id):
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
        form_layout.addRow("Unit Price ($):", self.unit_price_input)

        # Total Price (Read-Only)
        self.total_price_label = QLineEdit("0.00")
        self.total_price_label.setReadOnly(True)
        form_layout.addRow("Total Price ($):", self.total_price_label)

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
        total = quantity * unit_price
        self.total_price_label.setText(f"{total:.2f}")

    def load_existing_item(self):
        """Load existing item details for editing."""
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT description, quantity, unit_price FROM invoice_items WHERE item_id = ?
        ''', (self.item_id,))
        item = cursor.fetchone()
        conn.close()

        if item:
            self.description_input.setText(item[0])
            self.quantity_input.setValue(item[1])
            self.unit_price_input.setValue(item[2])
            self.calculate_total()

    def save_item(self):
        """Save or update the item in the database."""
        description = self.description_input.text().strip()
        quantity = self.quantity_input.value()
        unit_price = self.unit_price_input.value()
        total_price = quantity * unit_price

        if not description:
            QMessageBox.warning(self, "Input Error", "Please enter a valid description.")
            return

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()

        if self.item_id:
            cursor.execute('''
                UPDATE invoice_items SET description = ?, quantity = ?, unit_price = ?, total_price = ?
                WHERE item_id = ?
            ''', (description, quantity, unit_price, total_price, self.item_id))
        else:
            cursor.execute('''
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.invoice_id, description, quantity, unit_price, total_price))

        conn.commit()
        conn.close()
        self.accept()

class BillingInvoicingScreen(QWidget):
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

        layout.addLayout(filter_layout)

        # Invoice Table
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(9)
        self.invoice_table.setHorizontalHeaderLabels([
            "Invoice ID", "Appointment ID", "Patient Name", "Total Amount",
            "Final Amount", "Payment Status", "Payment Method", "Remaining Balance", "Created At"
        ])
        self.invoice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.invoice_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.invoice_table.itemSelectionChanged.connect(self.load_selected_invoice)
        layout.addWidget(self.invoice_table)

        # Summary Section
        self.summary_section = QHBoxLayout()
        self.total_amount_label = QLabel("Total Amount: $0.00")
        self.remaining_balance_label = QLabel("Remaining Balance: $0.00")
        self.payment_count_label = QLabel("Payments: 0")
        self.summary_section.addWidget(self.total_amount_label)
        self.summary_section.addWidget(self.remaining_balance_label)
        self.summary_section.addWidget(self.payment_count_label)

        layout.addLayout(self.summary_section)


        # Itemized Billing Table
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(4)
        self.item_table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit Price", "Total Price"])
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

        self.appointment_id_input = QLineEdit()
        self.appointment_id_input.setPlaceholderText("Enter Appointment ID")
        self.appointment_id_input.textChanged.connect(self.fetch_patient_details)
        form_layout.addRow("Appointment ID:", self.appointment_id_input)

        self.patient_name_label = QLineEdit()
        self.patient_name_label.setReadOnly(True)
        form_layout.addRow("Patient Name:", self.patient_name_label)

        self.total_amount_input = QLineEdit()
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
        form_layout.addRow("Final Amount:", self.final_amount_label)

        # Remaining Balance
        self.remaining_balance_label = QLineEdit()
        self.remaining_balance_label.setReadOnly(True)
        form_layout.addRow("Remaining Balance:", self.remaining_balance_label)

        self.payment_status_dropdown = QComboBox()
        self.payment_status_dropdown.addItems(["Unpaid", "Paid", "Partially Paid"])
        form_layout.addRow("Payment Status:", self.payment_status_dropdown)

        self.payment_method_dropdown = QComboBox()  # ✅ FIXED: Using the correct attribute
        self.payment_method_dropdown.addItems(["Cash", "Card", "Bank Transfer", "Other"])
        form_layout.addRow("Payment Method:", self.payment_method_dropdown)

        layout.addLayout(form_layout)

        # Buttons for actions
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create Invoice")
        self.create_button.clicked.connect(self.create_invoice)

        self.edit_button = QPushButton("Edit Invoice")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_invoice)

        self.view_payments_button = QPushButton("View Payments")
        self.view_payments_button.setEnabled(False)
        self.view_payments_button.clicked.connect(self.view_payment_history)

        self.add_payment_button = QPushButton("Add Payment")
        self.add_payment_button.setEnabled(False)
        self.add_payment_button.clicked.connect(self.add_payment)

        self.delete_button = QPushButton("Delete Invoice")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_invoice)

        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.view_payments_button)
        button_layout.addWidget(self.add_payment_button)
        button_layout.addWidget(self.delete_button)

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
            self.load_invoices()  # Refresh invoices after payment

    def load_invoices(self):
        """Load all invoices into the table with appointment-specific data."""
        try:
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.invoice_id, i.appointment_id, (SELECT name FROM patients WHERE patient_id = a.patient_id),
                       i.total_amount, i.final_amount, i.payment_status, i.payment_method,
                       (i.final_amount - COALESCE((SELECT SUM(amount_paid) FROM payment_history WHERE invoice_id = i.invoice_id), 0)),
                       i.created_at
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
        """Filter and display invoices based on search text and status."""
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()

        filtered_invoices = []
        total_amount = 0
        remaining_balance = 0
        payment_count = 0

        for invoice in self.invoices:
            invoice_id, appointment_id, patient_name, total_amt, final_amt, status, _, balance, _ = invoice
            if search_text and search_text not in str(invoice_id).lower() and search_text not in patient_name.lower():
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
            self.invoice_table.insertRow(self.invoice_table.rowCount())
            for col_index, col_data in enumerate(row_data):
                self.invoice_table.setItem(self.invoice_table.rowCount() - 1, col_index, QTableWidgetItem(str(col_data)))

        # Update summary
        self.total_amount_label.setText(f"Total Amount: ${total_amount:.2f}")
        self.remaining_balance_label.setText(f"Remaining Balance: ${remaining_balance:.2f}")
        self.payment_count_label.setText(f"Payments: {payment_count}")

    def load_selected_invoice(self):
        """Load selected invoice details into the form."""
        selected_row = self.invoice_table.currentRow()
        if selected_row < 0:
            return

        self.selected_invoice_id = int(self.invoice_table.item(selected_row, 0).text())
        self.appointment_id_input.setText(self.invoice_table.item(selected_row, 1).text())
        self.patient_name_label.setText(self.invoice_table.item(selected_row, 2).text())
        self.total_amount_input.setText(self.invoice_table.item(selected_row, 3).text())
        self.final_amount_label.setText(self.invoice_table.item(selected_row, 4).text())
        self.payment_status_dropdown.setCurrentText(self.invoice_table.item(selected_row, 5).text())
        self.payment_method_dropdown.setCurrentText(self.invoice_table.item(selected_row, 6).text())

        # Enable buttons only when an invoice is selected
        self.edit_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.view_payments_button.setEnabled(True)
        self.add_payment_button.setEnabled(True)  # ✅ Fix: Ensure Add Payment button is enabled

        self.selected_invoice_id = int(self.invoice_table.item(selected_row, 0).text())
        self.add_item_button.setEnabled(True)
        self.load_invoice_items()

    def load_invoice_items(self):
        """Load itemized billing for selected invoice."""
        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT description, quantity, unit_price, total_price FROM invoice_items WHERE invoice_id = ?
        ''', (self.selected_invoice_id,))
        items = cursor.fetchall()
        conn.close()

        self.item_table.setRowCount(0)
        for row_data in items:
            self.item_table.insertRow(self.item_table.rowCount())
            for col_index, col_data in enumerate(row_data):
                self.item_table.setItem(self.item_table.rowCount() - 1, col_index, QTableWidgetItem(str(col_data)))

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
        """Open Add Item Dialog."""
        dialog = ItemizedBillingDialog(self.selected_invoice_id)
        if dialog.exec():
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
            return

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.appointment_id = ?
        ''', (appointment_id,))
        patient = cursor.fetchone()
        conn.close()

        if patient:
            self.patient_name_label.setText(patient[0])
        else:
            self.patient_name_label.clear()

    def create_invoice(self):
        """Create a new invoice and store items in the database."""
        try:
            appointment_id = self.appointment_id_input.text().strip()
            total_amount = self.total_amount_input.text().strip()
            tax = self.tax_input.value()
            discount = self.discount_input.value()
            payment_status = self.payment_status_dropdown.currentText()
            payment_method = self.payment_method_dropdown.currentText()

            if not appointment_id:
                QMessageBox.warning(self, "Input Error", "Appointment ID is required.")
                return

            if not total_amount or float(total_amount) <= 0:
                QMessageBox.warning(self, "Input Error", "Total amount must be greater than zero.")
                return

            if self.item_table.rowCount() == 0:
                QMessageBox.warning(self, "Input Error", "At least one item must be added to the invoice.")
                return

            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()

            # **Check for duplicate invoices for the same appointment**
            cursor.execute("SELECT invoice_id FROM invoices WHERE appointment_id = ?", (appointment_id,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Duplicate Invoice", "An invoice already exists for this appointment.")
                conn.close()
                return

            # **Insert new invoice**
            cursor.execute('''
                INSERT INTO invoices (appointment_id, total_amount, tax, discount, final_amount, payment_status, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (appointment_id, total_amount, tax, discount, total_amount, payment_status, payment_method))

            invoice_id = cursor.lastrowid  # Get newly created invoice ID

            # **Insert all invoice items**
            for row in range(self.item_table.rowCount()):
                item_name = self.item_table.item(row, 0).text()
                quantity = int(self.item_table.item(row, 1).text())
                unit_price = float(self.item_table.item(row, 2).text())
                total = float(self.item_table.item(row, 3).text())

                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                    VALUES (?, ?, ?, ?, ?)
                ''', (invoice_id, item_name, quantity, unit_price, total))

            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", "Invoice created successfully.")
            self.load_invoices()
            self.clear_inputs()
            self.clear_invoice_form()  # ✅ Clear the form after creating an invoice
            pass

        except Exception as e:
            log_error(f"Error in create_invoice: {str(e)}")
            QMessageBox.critical(self, "Error", "Failed to create invoice.")

    def edit_invoice(self):
        """Edit an existing invoice and update associated items."""
        if not self.selected_invoice_id:
            QMessageBox.warning(self, "No Invoice Selected", "Please select an invoice to edit.")
            return

        appointment_id = self.appointment_id_input.text()
        total_amount = self.total_amount_input.text()
        tax = self.tax_input.value()
        discount = self.discount_input.value()
        final_amount = self.final_amount_label.text()
        payment_status = self.payment_status_dropdown.currentText()
        payment_method = self.payment_method_dropdown.currentText()

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()

        # Update invoice details
        cursor.execute('''
            UPDATE invoices
            SET appointment_id = ?, total_amount = ?, tax = ?, discount = ?, final_amount = ?, 
                payment_status = ?, payment_method = ?
            WHERE invoice_id = ?
        ''', (appointment_id, total_amount, tax, discount, final_amount, payment_status, payment_method,
              self.selected_invoice_id))

        # Remove existing items and re-add them
        cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (self.selected_invoice_id,))

        for row in range(self.item_table.rowCount()):
            item_name = self.item_table.item(row, 0).text()
            quantity = int(self.item_table.item(row, 1).text())
            unit_price = float(self.item_table.item(row, 2).text())
            total = float(self.item_table.item(row, 3).text())

            cursor.execute('''
                INSERT INTO invoice_items (invoice_id, item_name, quantity, unit_price, total)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.selected_invoice_id, item_name, quantity, unit_price, total))

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Invoice updated successfully.")
        self.load_invoices()
        self.clear_inputs()
        self.clear_invoice_form()  # ✅ Clear the form after editing an invoice

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
        self.delete_button.setEnabled(False)
        self.view_payments_button.setEnabled(False)
        self.add_payment_button.setEnabled(False)

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