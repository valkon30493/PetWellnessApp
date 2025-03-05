from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout,
                               QMessageBox, QHeaderView)
from PySide6.QtCore import QTimer
import sqlite3
from datetime import datetime
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
        self.reminders_table.horizontalHeader().setFixedHeight(60)  # Adjust header height to accommodate wrapping

        self.reminders_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.reminders_table.setColumnCount(13)
        self.reminders_table.setHorizontalHeaderLabels([
            "Reminder ID",
            "Appointment Time",
            "Patient Name",
            "Owner Name",
            "Owner Contact",
            "Owner Email",
            "Type",
            "Reason",
            "Vet",
            "Appointment Status",
            "Reminder Time",
            "Status",
            "Reminder Reason"
        ])
        layout.addWidget(self.reminders_table)

        # Buttons for actions
        button_layout = QHBoxLayout()

        self.show_today_button = QPushButton("Today's Reminders")
        self.show_today_button.clicked.connect(lambda: self.load_reminders(show_all=False))
        button_layout.addWidget(self.show_today_button)

        # Button to show all reminders
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

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Timer for automatic notification checking
        self.notification_timer = QTimer(self)
        self.notification_timer.timeout.connect(self.check_and_send_notifications)
        self.notification_timer.start(60000)  # Check every 60 seconds

        # Load reminders when the screen is initialized
        self.load_reminders()

    def adjust_header_height(self):
        max_lines = 2  # Estimate maximum number of lines for wrapping
        line_height = 20  # Approximate height for each line
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
        """Check and send notifications for pending reminders."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()

        # Query for reminders with status "Pending" and time <= current time
        cursor.execute('''
            SELECT r.reminder_id, r.reminder_time, r.reminder_reason,
                   p.owner_email, p.owner_name, a.appointment_type, a.reason
            FROM reminders r
            JOIN appointments a ON r.appointment_id = a.appointment_id
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE r.reminder_time <= ? AND r.reminder_status = 'Pending'
        ''', (current_time,))
        reminders = cursor.fetchall()

        for reminder in reminders:
            reminder_id, reminder_time, reminder_reason, owner_email, owner_name, appointment_type, appointment_reason = reminder

            if not owner_email:
                print(f"No email found for owner {owner_name}. Skipping notification.")
                continue

            subject = f"Reminder for Appointment"
            message = (
                f"Dear {owner_name},\n\n"
                f"This is a reminder for the appointment:\n"
                f"Time: {reminder_time}\n"
                f"Appointment Type: {appointment_type}\n"
                f"Reason: {appointment_reason}\n\n"
                f"Additional Notes: {reminder_reason}\n\n"
                f"Thank you!"
            )

            # Send email
            email_sent = send_email(owner_email, subject, message)

            # Update reminder status if email sent successfully
            if email_sent:
                cursor.execute('''
                    UPDATE reminders
                    SET reminder_status = 'Sent'
                    WHERE reminder_id = ?
                ''', (reminder_id,))

        conn.commit()
        conn.close()

        self.load_reminders()  # Refresh the table
        #  QMessageBox.information(self, "Notifications Sent", "All pending notifications have been processed.")

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
