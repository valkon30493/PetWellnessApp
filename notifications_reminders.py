from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout,
                               QMessageBox, QHeaderView, QInputDialog)
from PySide6.QtCore import QTimer
import sqlite3
from datetime import datetime, timedelta
from notifications import send_email

class NotificationsRemindersScreen(QWidget):
    def __init__(self):
        super().__init__()

        # Main layout
        layout = QVBoxLayout()

        # Table for reminders
        self.reminders_table = QTableWidget()
        # Enable wrapping and adjust header style
        self.reminders_table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                white-space: normal; /* Allow multiline text */
                padding: 4px;        /* Add padding for better spacing */
                font-size: 12px;     /* Adjust font size */
            }
        """)
        self.adjust_header_height()
        self.reminders_table.horizontalHeader().setFixedHeight(60)
        self.reminders_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.reminders_table.setColumnCount(13)
        self.reminders_table.setHorizontalHeaderLabels([
            "Reminder ID", "Appointment Time", "Patient Name", "Owner Name",
            "Owner Contact", "Owner Email", "Type", "Reason", "Vet",
            "Appointment Status", "Reminder Time", "Status", "Reminder Reason"
        ])
        layout.addWidget(self.reminders_table)

        # Buttons for actions
        button_layout = QHBoxLayout()
        self.show_today_button = QPushButton("Today's Reminders")
        self.show_today_button.clicked.connect(lambda: self.load_reminders(show_all=False))
        button_layout.addWidget(self.show_today_button)

        self.show_all_button = QPushButton("All Reminders")
        self.show_all_button.clicked.connect(lambda: self.load_reminders(show_all=True))
        button_layout.addWidget(self.show_all_button)

        self.check_notifications_button = QPushButton("Check & Send Notifications")
        self.check_notifications_button.clicked.connect(self.check_and_send_notifications)
        button_layout.addWidget(self.check_notifications_button)

        self.mark_triggered_button = QPushButton("Mark as Triggered")
        self.mark_triggered_button.clicked.connect(self.mark_as_triggered)
        button_layout.addWidget(self.mark_triggered_button)

        self.delete_button = QPushButton("Delete Reminder")
        self.delete_button.clicked.connect(self.delete_reminder)
        button_layout.addWidget(self.delete_button)

        self.snooze_button = QPushButton("Snooze")
        self.snooze_button.clicked.connect(self.snooze_reminder)
        button_layout.addWidget(self.snooze_button)


        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Timer for automatic notification checking
        self.notification_timer = QTimer(self)
        self.notification_timer.timeout.connect(self.check_and_send_notifications)
        self.notification_timer.start(60000)  # every 60s

        # Initial load
        self.load_reminders()

    def snooze_reminder(self):
        row = self.reminders_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Reminder Selected", "Select one first.")
            return
        rem_id = int(self.reminders_table.item(row, 0).text())
        minutes, ok = QInputDialog.getInt(self, "Snooze", "Snooze by how many minutes?", 15, 1, 720)
        if not ok:
            return
        new_dt = datetime.now() + timedelta(minutes=minutes)
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE reminders
               SET reminder_time = ?, reminder_status = 'Pending'
             WHERE reminder_id = ?
        """, (new_dt.strftime("%Y-%m-%d %H:%M:%S"), rem_id))
        conn.commit()
        conn.close()
        self.load_reminders()


    def adjust_header_height(self):
        max_lines = 2
        line_height = 20
        self.reminders_table.horizontalHeader().setFixedHeight(max_lines * line_height)

    def reload_reminders(self):
        """Wrapper for refreshing the reminders table."""
        self.load_reminders()

    def load_reminders(self, show_all=False):
        """Load reminders into the table. By default, show only today's reminders."""
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()

        # Base query
        query = '''
            SELECT 
                r.reminder_id,
                a.date_time AS appointment_time,
                p.name AS patient_name,
                p.owner_name AS owner_name,
                p.owner_contact AS owner_contact,
                p.owner_email AS owner_email,
                a.appointment_type AS appointment_type,
                a.reason AS appointment_reason,
                a.veterinarian AS assigned_vet,
                a.status AS appointment_status,
                r.reminder_time,
                r.reminder_status,
                r.reminder_reason
            FROM reminders r
            JOIN appointments a ON r.appointment_id = a.appointment_id
            JOIN patients p ON a.patient_id = p.patient_id
        '''
        params = []

        # Filter for today's reminders if not showing all
        if not show_all:
            today = datetime.now().strftime("%Y-%m-%d")
            query += " WHERE DATE(r.reminder_time) = ?"
            params.append(today)

        cursor.execute(query, params)
        reminders = cursor.fetchall()
        conn.close()

        # Populate the table
        self.reminders_table.setRowCount(0)
        for row_index, row_data in enumerate(reminders):
            self.reminders_table.insertRow(row_index)
            for col_index, col_data in enumerate(row_data):
                self.reminders_table.setItem(row_index, col_index, QTableWidgetItem(str(col_data)))

    def check_and_send_notifications(self):
        """Check & send notifications for pending reminders (appointments + invoices)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()

        # Fetch all pending reminders up to now
        cursor.execute('''
            SELECT r.reminder_id,
                   r.appointment_id,
                   r.reminder_time,
                   r.reminder_reason,
                   p.owner_email,
                   p.owner_name,
                   a.appointment_type,
                   a.reason
              FROM reminders r
              JOIN appointments a ON r.appointment_id = a.appointment_id
              JOIN patients p     ON a.patient_id   = p.patient_id
             WHERE r.reminder_time <= ?
               AND r.reminder_status = 'Pending'
        ''', (now,))
        reminders = cursor.fetchall()

        for (rem_id, appt_id, rem_time, rem_reason,
             owner_email, owner_name, appt_type, appt_reason) in reminders:

            if not owner_email:
                print(f"No email for {owner_name}, skipping.")
                continue

            # Default: appointment reminder
            subject = "Reminder for Appointment"
            message = (
                f"Dear {owner_name},\n\n"
                f"This is a reminder for your appointment:\n"
                f"Time: {rem_time}\n"
                f"Type: {appt_type}\n"
                f"Reason: {appt_reason}\n\n"
                f"Notes: {rem_reason}\n\n"
                "Thank you!"
            )

            # If this is an *invoice* reminder (by convention)
            if rem_reason.lower().startswith("invoice"):
                # Look up invoice status & remaining balance
                cursor.execute('''
                    SELECT final_amount - COALESCE((
                        SELECT SUM(amount_paid)
                          FROM payment_history
                         WHERE invoice_id = i.invoice_id
                    ),0),
                    payment_status
                      FROM invoices i
                     WHERE i.appointment_id = ?
                ''', (appt_id,))
                row = cursor.fetchone()
                if row:
                    remaining, pay_stat = row
                    # If already paid, mark this reminder Sent and skip
                    if pay_stat == "Paid" or remaining <= 0:
                        cursor.execute('''
                            UPDATE reminders
                               SET reminder_status = 'Sent'
                             WHERE reminder_id = ?
                        ''', (rem_id,))
                        continue

                    # Otherwise override email content
                    subject = "Invoice Payment Reminder"
                    message = (
                        f"Dear {owner_name},\n\n"
                        f"Your invoice for appointment #{appt_id} is due.\n"
                        f"Remaining balance: €{remaining:.2f}\n\n"
                        f"Notes: {rem_reason}\n\n"
                        "Thank you!"
                    )

            # Send the email
            sent = send_email(owner_email, subject, message)
            if sent:
                cursor.execute('''
                    UPDATE reminders
                       SET reminder_status = 'Sent'
                     WHERE reminder_id = ?
                ''', (rem_id,))

        conn.commit()
        conn.close()
        self.load_reminders()

    def mark_as_triggered(self):
        """Mark selected reminder as triggered."""
        selected_row = self.reminders_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "No Reminder Selected", "Please select a reminder to mark as triggered.")
            return

        reminder_id = int(self.reminders_table.item(selected_row, 0).text())
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reminders
            SET reminder_status = ?
            WHERE reminder_id = ?
        ''', ('Triggered', reminder_id))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Reminder marked as triggered.")
        self.load_reminders()

    def delete_reminder(self):
        """Delete selected reminder."""
        selected_row = self.reminders_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "No Reminder Selected", "Please select a reminder to delete.")
            return

        reminder_id = int(self.reminders_table.item(selected_row, 0).text())
        reply = QMessageBox.question(self, "Delete Confirmation", "Are you sure you want to delete this reminder?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect('vet_management.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM reminders WHERE reminder_id = ?', (reminder_id,))
            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", "Reminder deleted successfully.")
            self.load_reminders()
