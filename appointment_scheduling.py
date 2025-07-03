import sqlite3
import csv
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget, QTableWidgetItem,
                               QLineEdit, QComboBox, QPushButton,  QMessageBox, QCompleter
                               , QDateEdit, QLabel, QFileDialog, QCalendarWidget, QTimeEdit, QDialog, QDateTimeEdit,
                               QHeaderView)
from PySide6.QtCore import Qt, QDate, QStringListModel, QTime, Signal, QTimer
from PySide6.QtGui import QColor, QTextCharFormat, QBrush
from notifications import send_email
from logger import log_error  # Import the log_error function

class MultiSelectCalendar(QCalendarWidget):
    def __init__(self):
        super().__init__()
        self.selected_dates = set()

        # 1. Month/Year label
        self.header = QLabel()
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_header(self.yearShown(), self.monthShown())
        self.currentPageChanged.connect(self.update_header)

        # 2. Grid & week numbers
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
        # 3. Disable past
        self.setMinimumDate(QDate.currentDate())

        # Highlight format
        self._fmt = QTextCharFormat()
        self._fmt.setBackground(QBrush(QColor("#cfe2f3")))

        # hook clicks
        self.clicked.connect(self.toggle_date)

    def update_header(self, year: int, month: int):
        # Update the month/year label
        d = QDate(year, month, 1)
        self.header.setText(d.toString("MMMM yyyy"))

    def toggle_date(self, date: QDate):
        if date in self.selected_dates:
            self.selected_dates.remove(date)
            self.setDateTextFormat(date, QTextCharFormat())
        else:
            self.selected_dates.add(date)
            self.setDateTextFormat(date, self._fmt)

    def get_selected_dates(self):
        return sorted(self.selected_dates)

class AppointmentSchedulingScreen(QWidget):
    # Signal to notify patient list updates
    reminders_list_updated = Signal()
    navigate_to_billing_signal = Signal(int)
    def __init__(self):
        super().__init__()

        # Initialize selected appointment ID
        self.selected_appointment_id = None

        self.notification_timer = QTimer(self)
        self.notification_timer.timeout.connect(self.check_and_send_notifications)
        self.notification_timer.start(60000)  # Check every minute

        # Main layout
        layout = QVBoxLayout()

        # Search layout for Patient Name and Appointment ID
        search_layout = QHBoxLayout()

        # Input for Patient Name
        self.search_patient_name_input = QLineEdit()
        self.search_patient_name_input.setPlaceholderText("Search by Patient Name")
        search_layout.addWidget(QLabel("Patient Name:"))
        search_layout.addWidget(self.search_patient_name_input)

        # Input for Appointment ID
        self.search_appointment_id_input = QLineEdit()
        self.search_appointment_id_input.setPlaceholderText("Search by Appointment ID")
        search_layout.addWidget(QLabel("Appointment ID:"))
        search_layout.addWidget(self.search_appointment_id_input)

        # Search and Clear buttons
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_appointments)
        search_layout.addWidget(self.search_button)

        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.clicked.connect(self.load_appointments)
        search_layout.addWidget(self.clear_search_button)

        # Add the search layout to the main layout
        layout.addLayout(search_layout)

        # Form layout for appointment details
        form_layout = QFormLayout()



        # Existing patient input
        self.patient_input = QLineEdit()
        self.patient_input.setPlaceholderText("Search for a patient...")
        self.patient_completer = QCompleter()
        self.patient_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # Correct usage
        self.patient_input.setCompleter(self.patient_completer)
        self.patient_input.textChanged.connect(self.filter_patients)
        form_layout.addRow("Patient:", self.patient_input)

        # set up the “multi_calendar” attribute before you ever use it
        self.multi_calendar = MultiSelectCalendar()
        form_layout.addRow("", self.multi_calendar.header)
        form_layout.addRow("Select Dates:", self.multi_calendar)

        # Time picker for selecting appointment time
        self.time_picker = QTimeEdit()
        self.time_picker.setTime(QTime.currentTime())  # Default to the current time
        form_layout.addRow("Time:", self.time_picker)

        # Duration dropdown
        self.duration_dropdown = QComboBox()
        self.duration_dropdown.addItems(["15", "30", "45", "60"])
        self.duration_dropdown.setCurrentText("30")
        form_layout.addRow("Duration (min):", self.duration_dropdown)

        # Appointment type dropdown
        self.type_dropdown = QComboBox()
        self.type_dropdown.addItems(["General", "Examination", "Consultation", "Follow-Up", "Surgery"])
        form_layout.addRow("Appointment Type:", self.type_dropdown)

        # Reason for the visit
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Reason for Visit")
        form_layout.addRow("Reason:", self.reason_input)

        # Assigned veterinarian dropdown
        self.vet_dropdown = QComboBox()
        self.vet_dropdown.addItem("Select Veterinarian")
        self.vet_dropdown.addItems(["Dr. Souzana", "Dr. Klio"])  # Example veterinarians
        form_layout.addRow("Veterinarian:", self.vet_dropdown)

        # Status dropdown for appointment status
        self.status_dropdown = QComboBox()
        self.status_dropdown.addItems(["Scheduled", "To be Confirmed", "Completed", "No-show", "Canceled"])
        form_layout.addRow("Status:", self.status_dropdown)

        # Add form layout to main layout
        layout.addLayout(form_layout)

        # Filtering options layout
        filter_layout = QHBoxLayout()

        # Date range filters
        self.start_date_filter = QDateEdit()
        self.start_date_filter.setCalendarPopup(True)
        self.start_date_filter.setDate(QDate.currentDate())
        filter_layout.addWidget(QLabel("Start Date:"))
        filter_layout.addWidget(self.start_date_filter)

        self.end_date_filter = QDateEdit()
        self.end_date_filter.setCalendarPopup(True)
        self.end_date_filter.setDate(QDate.currentDate())
        filter_layout.addWidget(QLabel("End Date:"))
        filter_layout.addWidget(self.end_date_filter)

        # Status filter
        self.status_filter = QComboBox()
        self.status_filter.addItem("All")
        self.status_filter.addItems(["Scheduled", "To be Confirmed", "Completed", "No-show", "Canceled"])
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_filter)

        # Search button for filters
        search_button = QPushButton("Apply Filters")
        search_button.clicked.connect(self.apply_filters)
        filter_layout.addWidget(search_button)

        # Add filtering layout to main layout
        layout.addLayout(filter_layout)

        # Buttons for actions
        button_layout = QHBoxLayout()
        self.schedule_button = QPushButton("Schedule Appointment")
        self.schedule_button.clicked.connect(self.schedule_appointment)

        self.edit_button = QPushButton("Edit Appointment")
        self.edit_button.setEnabled(False)  # Initially disabled
        self.edit_button.clicked.connect(self.edit_appointment)

        self.complete_button = QPushButton("Mark as Completed")
        self.complete_button.setEnabled(False)  # Initially disabled
        self.complete_button.clicked.connect(self.mark_as_completed)

        self.create_invoice_button = QPushButton("Create Invoice")
        self.create_invoice_button.setEnabled(False)  # Initially disabled
        self.create_invoice_button.clicked.connect(self.navigate_to_billing)
        button_layout.addWidget(self.create_invoice_button)

        self.cancel_button = QPushButton("Cancel Appointment")
        self.cancel_button.setEnabled(False)  # Initially disabled
        self.cancel_button.clicked.connect(self.cancel_appointment)

        self.reminder_button = QPushButton("Set Reminder")
        self.reminder_button.setEnabled(False)  # Initially disabled until an appointment is selected
        self.reminder_button.clicked.connect(self.set_reminder)

        self.view_all_button = QPushButton("View All Appointments")
        self.view_all_button.clicked.connect(self.load_appointments)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self.export_to_csv)

        # Add buttons to layout
        button_layout.addWidget(self.schedule_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.complete_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.reminder_button)
        button_layout.addWidget(self.view_all_button)
        button_layout.addWidget(self.export_button)

        # Add buttons layout to main layout
        layout.addLayout(button_layout)

        # Table to display appointments
        self.appointment_table = QTableWidget()
        self.appointment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.appointment_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.appointment_table.setColumnCount(8)
        self.appointment_table.setHorizontalHeaderLabels([
            "ID", "Patient", "Date & Time (Dur)", "Type", "Reason", "Veterinarian", "Status", "Notification Status"
        ])
        self.appointment_table.itemSelectionChanged.connect(self.load_selected_appointment)
        self.appointment_table.setSortingEnabled(True)

        # Add table to main layout
        layout.addWidget(self.appointment_table)

        # Set the layout
        self.setLayout(layout)

        # Load all patient names for the completer
        self.all_patients = []  # Store all patients for filtering
        self.load_patients()
        self.load_appointments()

    def search_appointments(self):
        """Search appointments by Patient Name or Appointment ID (including duration)."""
        patient_name = self.search_patient_name_input.text().strip()
        appointment_id = self.search_appointment_id_input.text().strip()

        # Base query pulling duration + notification status
        query = """
            SELECT
                a.appointment_id,
                p.name,
                a.date_time,
                a.duration_minutes,
                a.appointment_type,
                a.reason,
                a.veterinarian,
                a.status,
                a.notification_status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE 1=1
        """
        params = []
        if patient_name:
            query += " AND p.name LIKE ?"
            params.append(f"%{patient_name}%")
        if appointment_id:
            query += " AND a.appointment_id = ?"
            params.append(appointment_id)

        try:
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Clear & refill table
            self.appointment_table.setRowCount(0)
            for r, row in enumerate(rows):
                appt_id, patient, dt, dur, typ, reason, vet, status, notif = row
                self.appointment_table.insertRow(r)
                # ID
                self.appointment_table.setItem(r, 0, QTableWidgetItem(str(appt_id)))
                # Patient
                self.appointment_table.setItem(r, 1, QTableWidgetItem(patient))
                # Date & Time (Dur)
                self.appointment_table.setItem(r, 2, QTableWidgetItem(f"{dt} ({dur} min)"))
                # Type, Reason, Vet, Status, Notification
                for c, val in enumerate((typ, reason, vet, status, notif), start=3):
                    self.appointment_table.setItem(r, c, QTableWidgetItem(str(val)))

            if not rows:
                QMessageBox.information(self, "No Results", "No appointments found matching the search criteria.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while searching:\n{e}")

    def reload_patients(self):
        """Reload the patient list into the completer."""
        self.load_patients()
        QMessageBox.information(self, "Patient List Updated", "The patient list has been updated.")

    def load_patients(self):
        """Load patient names into the completer."""
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute("SELECT patient_id, name FROM patients")
        patients = cursor.fetchall()
        conn.close()

        self.all_patients = [(str(patient_id), name) for patient_id, name in patients]

        # Populate the completer with patient names
        patient_names = [f"{name} (ID: {patient_id})" for patient_id, name in self.all_patients]
        model = QStringListModel(patient_names)  # Convert list to a model
        self.patient_completer.setModel(model)

    def filter_patients(self, text):
        """Filter patients based on input text."""
        # Create a filtered list of patients
        filtered_patients = [
            f"{name} (ID: {patient_id})"
            for patient_id, name in self.all_patients
            if text.lower() in name.lower()
        ]

        # Wrap the filtered list in a QStringListModel
        model = QStringListModel(filtered_patients)
        self.patient_completer.setModel(model)

    def schedule_appointment(self):
        """Schedule new appointments for selected dates."""
        try:
            patient_text = self.patient_input.text()
            if not patient_text or "(" not in patient_text or ")" not in patient_text:
                QMessageBox.warning(self, "Input Error", "Please select a valid patient.")
                return

            patient_id = int(patient_text.split("(ID: ")[1][:-1])  # Extract patient ID
            selected_dates = self.multi_calendar.get_selected_dates()
            appointment_type = self.type_dropdown.currentText()
            reason = self.reason_input.text()
            vet = self.vet_dropdown.currentText()
            status = self.status_dropdown.currentText()
            selected_time = self.time_picker.time().toString("HH:mm")
            duration = int(self.duration_dropdown.currentText())  # ← new

            if not selected_dates:
                QMessageBox.warning(self, "Input Error", "Please select at least one date.")
                return

            if vet == "Select Veterinarian" or not reason:
                QMessageBox.warning(self, "Input Error", "Please fill out all required fields.")
                return



            conn = sqlite3.connect('vet_management.db')
            cursor = conn.cursor()
            count = 0

            for date in selected_dates:
                # 1) build start/end strings
                dt_start_str = f"{date.toString('yyyy-MM-dd')} {selected_time}"
                dt_start = datetime.strptime(dt_start_str, "%Y-%m-%d %H:%M")
                dt_end = dt_start + timedelta(minutes=duration)
                dt_end_str = dt_end.strftime("%Y-%m-%d %H:%M")

                # 2) conflict check
                cursor.execute("""
                                SELECT COUNT(*) 
                                  FROM appointments
                                 WHERE veterinarian = ?
                                   AND datetime(date_time, '+' || duration_minutes || ' minutes') > ?
                                   AND date_time < ?
                            """, (vet, dt_start_str, dt_end_str))
                (conflicts,) = cursor.fetchone()
                if conflicts:
                    QMessageBox.warning(
                        self,
                        "Scheduling Conflict",
                        f"{vet} already booked overlapping {dt_start_str}–{dt_end_str}"
                    )
                    continue

                # 3) if no conflict, insert
                cursor.execute('''
                                INSERT INTO appointments
                                  (patient_id, date_time, duration_minutes,
                                   appointment_type, reason, veterinarian, status, notification_status)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'Not Sent')
                            ''', (patient_id, dt_start_str, duration,
                                  appointment_type, reason, vet, status))
                count += 1

            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", f"Scheduled {count} new appointment(s).")
            self.load_appointments()
            self.clear_inputs()

        except Exception as e:
            log_error(f"Error scheduling appointment: {e}")
            QMessageBox.critical(self, "Error", "Failed to schedule appointment.")

    def edit_appointment(self):
        """Edit selected appointment data in the database, with conflict detection."""
        if not self.selected_appointment_id:
            QMessageBox.warning(self, "No Appointment Selected", "Please select an appointment to edit.")
            return

        # ── Validate patient selection ─────────────────────────────────────────
        patient_text = self.patient_input.text().strip()
        if "(" not in patient_text or ")" not in patient_text:
            QMessageBox.warning(self, "Input Error", "Please select a valid patient.")
            return
        patient_id = int(patient_text.split("(ID: ")[1].rstrip(")"))

        # ── Exactly one date for editing ──────────────────────────────────────
        dates = self.multi_calendar.get_selected_dates()
        if len(dates) != 1:
            QMessageBox.warning(self, "Input Error", "Please select exactly one date for editing.")
            return

        # ── Gather updated fields ─────────────────────────────────────────────
        sel_date = dates[0]
        sel_time = self.time_picker.time().toString("HH:mm")
        date_time = f"{sel_date.toString('yyyy-MM-dd')} {sel_time}"
        duration = int(self.duration_dropdown.currentText())
        appt_type = self.type_dropdown.currentText()
        reason = self.reason_input.text().strip()
        vet = self.vet_dropdown.currentText()
        status = self.status_dropdown.currentText()

        if vet == "Select Veterinarian" or not reason:
            QMessageBox.warning(self, "Input Error", "Please fill out all required fields.")
            return

        # ── Compute new appointment end time ─────────────────────────────────
        dt_start = datetime.strptime(date_time, "%Y-%m-%d %H:%M")
        dt_end = dt_start + timedelta(minutes=duration)
        dt_start_str = dt_start.strftime("%Y-%m-%d %H:%M")
        dt_end_str = dt_end.strftime("%Y-%m-%d %H:%M")

        conn = sqlite3.connect("vet_management.db")
        cursor = conn.cursor()

        # ── Conflict check (exclude the current appointment) ─────────────────
        cursor.execute("""
            SELECT COUNT(*) 
              FROM appointments
             WHERE veterinarian = ?
               AND appointment_id != ?
               AND datetime(date_time, '+' || duration_minutes || ' minutes') > ?
               AND date_time < ?
        """, (vet, self.selected_appointment_id, dt_start_str, dt_end_str))
        (conflicts,) = cursor.fetchone()
        if conflicts:
            QMessageBox.warning(
                self,
                "Scheduling Conflict",
                f"{vet} already has an overlapping appointment\n"
                f"between {dt_start_str} and {dt_end_str}."
            )
            conn.close()
            return

        # ── Preserve or reset notification status ────────────────────────────
        cursor.execute(
            "SELECT notification_status, date_time FROM appointments WHERE appointment_id = ?",
            (self.selected_appointment_id,)
        )
        notif_status, orig_dt = cursor.fetchone()
        if orig_dt != date_time:
            notif_status = "Not Sent"

        # ── Perform the update ───────────────────────────────────────────────
        cursor.execute("""
            UPDATE appointments
               SET patient_id         = ?,
                   date_time          = ?,
                   duration_minutes   = ?,
                   appointment_type   = ?,
                   reason             = ?,
                   veterinarian       = ?,
                   status             = ?,
                   notification_status= ?
             WHERE appointment_id = ?
        """, (
            patient_id, date_time, duration,
            appt_type, reason, vet, status,
            notif_status, self.selected_appointment_id
        ))

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Appointment updated successfully.")
        self.load_appointments()
        self.clear_inputs()

    def mark_as_completed(self):
        """Mark the selected appointment as completed"""
        if not self.selected_appointment_id:
            QMessageBox.warning(self,"No Appointment Selected", "Please select an appointment to mark as completed.")
            return

        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE appointments
            SET status = ?
            WHERE appointment_id = ?
            ''',("Completed",self.selected_appointment_id))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Appointment marked as completed.")

        self.load_appointments()
        self.clear_inputs()

    def cancel_appointment(self):
        """Cancel selected appointment."""
        if not self.selected_appointment_id:
            QMessageBox.warning(self, "No Appointment Selected", "Please select an appointment to cancel.")
            return

        reply = QMessageBox.question(
            self, "Cancel Confirmation",
            "Are you sure you want to cancel this appointment?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE appointments
            SET status = ?
            WHERE appointment_id = ?
        ''', ("Canceled", self.selected_appointment_id))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Appointment canceled successfully.")
        self.load_appointments()
        self.clear_inputs()

    def navigate_to_billing(self):
        """Navigate to Billing and Invoicing with the selected appointment details."""
        if not self.selected_appointment_id:
            QMessageBox.warning(self, "No Appointment Selected", "Please select an appointment.")
            return

        # Emit signal to pass data to the Billing and Invoicing screen
        appointment_id = self.selected_appointment_id
        self.navigate_to_billing_signal.emit(appointment_id)

    class ReminderDialog(QDialog):
        def __init__(self, appointment_id):
            super().__init__()
            self.setWindowTitle("Set Reminder")
            self.appointment_id = appointment_id

            # Layout and reminder time picker
            layout = QVBoxLayout()
            self.reminder_time_picker = QDateTimeEdit()
            self.reminder_time_picker.setCalendarPopup(True)
            cal = self.reminder_time_picker.calendarWidget()
            cal.setGridVisible(True)
            cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
            # (month/year header is already built in)

            layout.addWidget(QLabel("Reminder Date & Time:"))
            layout.addWidget(self.reminder_time_picker)

            # Reminder reason input
            self.reason_input = QLineEdit()
            self.reason_input.setPlaceholderText("Enter reminder reason (optional)")
            layout.addWidget(QLabel("Reason for Reminder:"))
            layout.addWidget(self.reason_input)

            # Save button
            save_button = QPushButton("Save Reminder")
            save_button.clicked.connect(self.save_reminder)
            layout.addWidget(save_button)

            self.setLayout(layout)

        def save_reminder(self):
            """Save the reminder to the database."""
            reminder_time = self.reminder_time_picker.dateTime().toString("yyyy-MM-dd HH:mm")
            reason = self.reason_input.text().strip()

            if not reminder_time:
                QMessageBox.warning(self, "Input Error", "Please select a valid reminder time.")
                return

            # Insert the reminder into the database
            conn = sqlite3.connect('vet_management.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reminders (appointment_id, reminder_time, reminder_reason, reminder_status)
                VALUES (?, ?, ?, ?)
            ''', (self.appointment_id, reminder_time, reason, 'Pending'))
            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", "Reminder set successfully.")
            self.accept()  # Close the dialog

    def set_reminder(self):
        """Open the ReminderDialog to set a reminder for the selected appointment."""
        if not self.selected_appointment_id:
            QMessageBox.warning(self, "No Appointment Selected", "Please select an appointment to set a reminder.")
            return

        dialog = self.ReminderDialog(self.selected_appointment_id)
        dialog.exec()  # Open the dialog
        # Emit the signal to notify updates
        self.reminders_list_updated.emit()

    def export_to_csv(self):
        """Export appointment data to a CSV file."""
        # Open a file dialog to select save location
        default_filename = f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", default_filename, "CSV Files (*.csv)")

        if not file_path:
            return  # User canceled

        # Fetch data from the table
        row_count = self.appointment_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "No Data", "There are no appointments to export.")
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                # Write headers
                headers = [self.appointment_table.horizontalHeaderItem(col).text() for col in
                           range(self.appointment_table.columnCount())]
                writer.writerow(headers)

                # Write rows
                for row in range(row_count):
                    row_data = [self.appointment_table.item(row, col).text() for col in
                                range(self.appointment_table.columnCount())]
                    writer.writerow(row_data)

            QMessageBox.information(self, "Export Successful", f"Appointments exported to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred: {str(e)}")

    def load_appointments(self):
        """Load all appointments into the table, including duration."""
        try:
            conn = sqlite3.connect("vet_management.db")
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    a.appointment_id,
                    p.name,
                    a.date_time,
                    a.duration_minutes,
                    a.appointment_type,
                    a.reason,
                    a.veterinarian,
                    a.status,
                    a.notification_status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
            """)
            rows = cur.fetchall()
            conn.close()

            self.appointment_table.setRowCount(0)
            for r, row in enumerate(rows):
                appt_id, patient, dt, dur, typ, reason, vet, status, notif = row
                self.appointment_table.insertRow(r)

                # col 0: ID
                self.appointment_table.setItem(r, 0, QTableWidgetItem(str(appt_id)))
                # col 1: Patient
                self.appointment_table.setItem(r, 1, QTableWidgetItem(patient))
                # col 2: Date & Time (Dur)
                display = f"{dt} ({dur} min)"
                self.appointment_table.setItem(r, 2, QTableWidgetItem(display))
                # cols 3–7: Type, Reason, Vet, Status, Notification
                for c, val in enumerate((typ, reason, vet, status, notif), start=3):
                    self.appointment_table.setItem(r, c, QTableWidgetItem(str(val)))
        except Exception as e:
            QMessageBox.critical(self, "Database Error",
                                 f"An error occurred while loading appointments:\n{e}")

    def apply_filters(self):
        """Apply date‐range + status filters to the appointment table (including duration)."""
        # build your date bounds
        start = self.start_date_filter.date().toString("yyyy-MM-dd") + " 00:00"
        end = self.end_date_filter.date().toString("yyyy-MM-dd") + " 23:59"
        status = self.status_filter.currentText()

        # SELECT 9 fields now
        query = """
            SELECT
                a.appointment_id,
                p.name,
                a.date_time,
                a.duration_minutes,
                a.appointment_type,
                a.reason,
                a.veterinarian,
                a.status,
                a.notification_status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.date_time BETWEEN ? AND ?
        """
        params = [start, end]
        if status != "All":
            query += " AND a.status = ?"
            params.append(status)

        try:
            conn = sqlite3.connect("vet_management.db")
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # clear out old data
            self.appointment_table.setRowCount(0)

            # repopulate
            for r, row in enumerate(rows):
                appt_id, patient, dt, dur, typ, reason, vet, stat, notif = row
                self.appointment_table.insertRow(r)
                # ID
                self.appointment_table.setItem(r, 0, QTableWidgetItem(str(appt_id)))
                # Patient
                self.appointment_table.setItem(r, 1, QTableWidgetItem(patient))
                # Date & Time (Dur)
                self.appointment_table.setItem(r, 2, QTableWidgetItem(f"{dt} ({dur} min)"))
                # Type, Reason, Vet, Status, Notification
                for c, val in enumerate((typ, reason, vet, stat, notif), start=3):
                    self.appointment_table.setItem(r, c, QTableWidgetItem(str(val)))

            if not rows:
                QMessageBox.information(self, "No Results", "No appointments found for those filters.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not apply filters:\n{e}")

    def load_selected_appointment(self):
        r = self.appointment_table.currentRow()
        if r < 0:
            return

        appt_id = int(self.appointment_table.item(r, 0).text())
        conn = sqlite3.connect("vet_management.db")
        cur = conn.cursor()
        cur.execute("""
            SELECT patient_id, date_time, duration_minutes,
                   appointment_type, reason, veterinarian, status
            FROM appointments
            WHERE appointment_id = ?
        """, (appt_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            QMessageBox.warning(self, "Error", "Could not load that appointment.")
            return

        patient_id, dt, dur, typ, reason, vet, status = row

        # Populate the form:
        # → Patient line (you already have a completer + formatting):
        name = next(n for pid, n in self.all_patients if pid == str(patient_id))
        self.patient_input.setText(f"{name} (ID: {patient_id})")

        # → Calendar & time
        date_part, time_part = dt.split(" ")
        self.multi_calendar.selected_dates = {QDate.fromString(date_part, "yyyy-MM-dd")}
        self.multi_calendar.update()
        self.time_picker.setTime(QTime.fromString(time_part, "HH:mm"))

        # → Duration
        self.duration_dropdown.setCurrentText(str(dur))

        # → Rest of the fields
        self.type_dropdown.setCurrentText(typ)
        self.reason_input.setText(reason)
        self.vet_dropdown.setCurrentText(vet)
        self.status_dropdown.setCurrentText(status)

        # Enable/disable buttons as before…
        self.schedule_button.setEnabled(False)
        self.edit_button.setEnabled(True)
        self.complete_button.setEnabled(status == "Scheduled")
        self.cancel_button.setEnabled(status not in ("Completed", "Canceled"))
        self.reminder_button.setEnabled(True)
        self.create_invoice_button.setEnabled(True)

        self.selected_appointment_id = appt_id

    def load_patient_details(self, patient_id, patient_name):
        """Load patient details into the appointment form."""
        self.clear_inputs()  # Clear existing form data
        self.patient_input.setText(f"{patient_name} (ID: {patient_id})")
        self.patient_input.setStyleSheet("background-color: lightyellow;")  # Highlight field

        # Reset the style after a delay
        QTimer.singleShot(3000, lambda: self.patient_input.setStyleSheet(""))

    def check_and_send_notifications(self):
        """Check for appointments 1 day in advance and send email notifications."""
        current_time = datetime.now()
        reminder_time = current_time + timedelta(days=1)
        reminder_start = reminder_time.strftime("%Y-%m-%d 00:00")
        reminder_end = reminder_time.strftime("%Y-%m-%d 23:59")

        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()

        # Query for appointments scheduled for the next day, including owner's name
        cursor.execute('''
            SELECT a.appointment_id, a.date_time, a.reason, a.status, 
                   p.owner_email, p.owner_name, p.name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE a.date_time BETWEEN ? AND ? AND a.notification_status = 'Not Sent'
        ''', (reminder_start, reminder_end))
        appointments = cursor.fetchall()

        for appointment in appointments:
            appointment_id, date_time, reason, status, email, owner_name, patient_name = appointment
            if not email:
                print(f"No email found for owner of patient {patient_name}. Skipping notification.")
                continue

            subject = f"Reminder: Appointment for {patient_name}"
            message = (
                f"Dear {owner_name},\n\n"
                f"This is a reminder for your upcoming appointment for {patient_name}:\n"
                f"Date & Time: {date_time}\n"
                f"Reason: {reason}\n\n"
                f"Status: {status}\n\n"
                f"Please contact us if you need to make changes.\n"
                f"Thank you!"
            )

            email_sent = send_email(email, subject, message)

            # Update notification status if email is sent
            if email_sent:
                cursor.execute('''
                    UPDATE appointments
                    SET notification_status = 'Sent'
                    WHERE appointment_id = ?
                ''', (appointment_id,))

        conn.commit()
        conn.close()

    def clear_inputs(self):
        """Clear all input fields and reset selected appointment."""
        # Clear patient input
        self.patient_input.clear()

        self.type_dropdown.setCurrentIndex(0)  # Reset to "Select Veterinarian"

        # Clear reason input
        self.reason_input.clear()

        # Reset veterinarian dropdown to the default value
        self.vet_dropdown.setCurrentIndex(0)  # Reset to "Select Veterinarian"

        # Reset status dropdown to the default value
        self.status_dropdown.setCurrentIndex(0)  # Reset to "Scheduled"

        # Clear selected dates from the MultiSelectCalendar
        self.multi_calendar.selected_dates.clear()
        self.multi_calendar.update()  # Refresh the calendar display

        # Reset the time picker to the current time
        self.time_picker.setTime(QTime.currentTime())

        # Reset duration back to default (30 min)
        self.duration_dropdown.setCurrentText("30")

        # Reset the selected appointment ID
        self.selected_appointment_id = None

        #  Enable the Schedule button
        self.schedule_button.setEnabled(True)

        # Disable action buttons
        self.edit_button.setEnabled(False)
        self.complete_button.setEnabled(False)
        self.cancel_button.setEnabled(False)