import sqlite3
import csv
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QTableWidget, QTableWidgetItem,
                               QLineEdit, QComboBox, QSpinBox, QPushButton, QMessageBox, QDialog, QDialogButtonBox,
                               QFileDialog, QHeaderView)
from PySide6.QtCore import Signal


class PatientManagementScreen(QWidget):
    # Signal to notify patient list updates
    patient_list_updated = Signal()
    patient_selected = Signal(int, str)  # Signal to pass patient ID and name

    def __init__(self):
        super().__init__()

        # Layout and form for patient details
        layout = QVBoxLayout()

        # Advanced search layout
        search_layout = QHBoxLayout()

        # Text search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, breed, or owner...")
        search_layout.addWidget(self.search_input)

        # Dropdown for species filter
        self.species_filter = QComboBox()
        self.species_filter.addItem("All Species")  # Default option
        self.species_filter.addItems(["Dog", "Cat", "Bird", "Reptile"])  # Example species
        search_layout.addWidget(self.species_filter)

        # Min Age filter
        self.min_age_filter = QSpinBox()
        self.min_age_filter.setRange(0, 100)  # Example range for ages
        self.min_age_filter.setPrefix("Min Age: ")
        search_layout.addWidget(self.min_age_filter)

        # Max Age filter
        self.max_age_filter = QSpinBox()
        self.max_age_filter.setRange(0, 100)
        self.max_age_filter.setPrefix("Max Age: ")
        search_layout.addWidget(self.max_age_filter)

        # Search button
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_patients)
        search_layout.addWidget(search_button)

        # Form layout for patient details
        form_layout = QFormLayout()
        age_layout = QHBoxLayout()

        self.name_input = QLineEdit()
        self.species_input = QLineEdit()
        self.breed_input = QLineEdit()
        # Input for years
        self.age_years_input = QSpinBox()
        self.age_years_input.setRange(0, 100)  # Example range
        self.age_years_input.setPrefix("Years: ")
        age_layout.addWidget(self.age_years_input)
        # Input for months
        self.age_months_input = QSpinBox()
        self.age_months_input.setRange(0, 11)  # Months: 0-11
        self.age_months_input.setPrefix("Months: ")
        age_layout.addWidget(self.age_months_input)
        # self.age_input = QLineEdit()
        self.owner_name_input = QLineEdit()
        self.owner_contact_input = QLineEdit()
        self.owner_email_input = QLineEdit()

        # Add fields to form layout
        form_layout.addRow("Patient Name:", self.name_input)
        form_layout.addRow("Species:", self.species_input)
        form_layout.addRow("Breed:", self.breed_input)
        # Add age layout to form
        form_layout.addRow("Age:", age_layout)
        # form_layout.addRow("Age:", self.age_input)
        form_layout.addRow("Owner Name:", self.owner_name_input)
        form_layout.addRow("Owner Contact:", self.owner_contact_input)
        form_layout.addRow("Owner Email:", self.owner_email_input)

        # Buttons for actions
        button_layout = QHBoxLayout()

        # Add Patient button
        self.add_button = QPushButton("Add Patient")
        self.add_button.clicked.connect(self.add_patient)


        # Edit Patient button
        self.edit_button = QPushButton("Edit Patient")
        self.edit_button.setEnabled(False)  # Initially disabled until a patient is selected
        self.edit_button.clicked.connect(self.update_patient)

        # Delete Patient button
        self.delete_button = QPushButton("Delete Patient")
        self.delete_button.setEnabled(False)  # Initially disabled until a patient is selected
        self.delete_button.clicked.connect(self.delete_patient)

        # View Details button
        self.view_button = QPushButton("View Details")
        self.view_button.setEnabled(False)  # Initially disabled until a patient is selected
        self.view_button.clicked.connect(self.view_details)

        # View All Patients button
        view_button = QPushButton("View All")
        view_button.clicked.connect(self.load_patients)

        # Export to CSV button
        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.export_to_csv)

        # Schedule appointment button
        self.schedule_appointment_button = QPushButton("Schedule Appointment")
        self.schedule_appointment_button.setEnabled(False)  # Initially disabled
        self.schedule_appointment_button.clicked.connect(self.navigate_to_appointment_scheduling)

        # Add buttons to layout
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.view_button)
        button_layout.addWidget(view_button)
        button_layout.addWidget(export_button)
        button_layout.addWidget(self.schedule_appointment_button)

        # Table to display patient records
        self.patient_table = QTableWidget()
        # Enable automatic resizing for horizontal and vertical headers
        self.patient_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.patient_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.patient_table.setColumnCount(8)
        self.patient_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Species", "Breed", "Age", "Owner Name", "Owner Contact", "Owner Email"])
        self.patient_table.itemSelectionChanged.connect(self.load_selected_patient)

        # Add layouts to main layout
        layout.addLayout(search_layout)  # Add search bar at the top
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.patient_table)

        self.setLayout(layout)

        # Track the selected patient's ID for editing
        self.selected_patient_id = None

    # Include all methods for add, update, delete, view, and search patients
    # These methods remain unchanged from your current implementation.
    def add_patient(self):
        """Insert new patient data into the database."""
        # Retrieve data from input fields
        name = self.name_input.text()
        species = self.species_input.text()
        breed = self.breed_input.text()
        age_years = self.age_years_input.value()
        age_months = self.age_months_input.value()
        owner_name = self.owner_name_input.text()
        owner_contact = self.owner_contact_input.text()
        owner_email = self.owner_email_input.text()

        # Ensure required fields are filled out
        if not (name and species and owner_name):
            QMessageBox.warning(self, "Input Error", "Please fill out all required fields.")
            return

        # Insert new patient record
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO patients (name, species, breed, age_years, age_months, owner_name, owner_contact, owner_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, species, breed, age_years, age_months, owner_name, owner_contact, owner_email))
        conn.commit()
        conn.close()

        # Emit the signal to notify updates
        self.patient_list_updated.emit()

        # Refresh table
        self.load_patients()

        QMessageBox.information(self, "Success", "Patient added successfully.")

    def update_patient(self):
        """Update selected patient data in the database."""
        if not self.selected_patient_id:
            QMessageBox.warning(self, "No Patient Selected", "Please select a patient to edit.")
            return

        # Debugging: Print the selected patient ID to ensure it's set correctly
        print("Updating patient with ID:", self.selected_patient_id)

        # Retrieve updated data from input fields
        name = self.name_input.text()
        species = self.species_input.text()
        breed = self.breed_input.text()
        age_years = self.age_years_input.value()
        age_months = self.age_months_input.value()
        # age = self.age_input.text()
        owner_name = self.owner_name_input.text()
        owner_contact = self.owner_contact_input.text()
        owner_email = self.owner_email_input.text()

        # Update the patient's information in the database
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE patients
            SET name = ?, species = ?, breed = ?, age_years = ?, age_months = ?, owner_name = ?, owner_contact = ?, owner_email = ?
            WHERE patient_id = ?
        ''', (name, species, breed, age_years, age_months, owner_name, owner_contact, owner_email, self.selected_patient_id))
        conn.commit()
        conn.close()

        # Clear inputs, reset selection, and refresh the table
        self.clear_inputs()
        self.load_patients()
        self.selected_patient_id = None
        self.edit_button.setEnabled(False)  # Disable edit until another selection is made

    def delete_patient(self):
        """Delete selected patient data from the database."""
        if not self.selected_patient_id:
            QMessageBox.warning(self, "No Patient Selected", "Please select a patient to delete.")
            return

        # Show confirmation dialog
        reply = QMessageBox.question(self, "Delete Confirmation",
                                     "Are you sure you want to delete this patient?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # Delete the patient's record from the database
            conn = sqlite3.connect('vet_management.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patients WHERE patient_id = ?", (self.selected_patient_id,))
            conn.commit()
            conn.close()

            # Clear inputs, reset selection, and refresh the table
            self.clear_inputs()
            self.load_patients()
            self.selected_patient_id = None
            self.edit_button.setEnabled(False)  # Disable edit button
            self.delete_button.setEnabled(False)  # Disable delete button

    def view_details(self):
        """Display selected patient details in a read-only modal dialog."""
        if not self.selected_patient_id:
            QMessageBox.warning(self, "No Patient Selected", "Please select a patient to view details.")
            return

        # Fetch selected patient details from the database
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, species, breed, age_years, age_months, owner_name, owner_contact, owner_email
            FROM patients
            WHERE patient_id = ?
        """, (self.selected_patient_id,))
        patient = cursor.fetchone()
        conn.close()

        if not patient:
            QMessageBox.warning(self, "Error", "Could not retrieve patient details.")
            return

        # Create the details dialog
        details_dialog = QDialog(self)
        details_dialog.setWindowTitle("Patient Details")

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Name: {patient[0]}"))
        layout.addWidget(QLabel(f"Species: {patient[1]}"))
        layout.addWidget(QLabel(f"Breed: {patient[2]}"))
        layout.addWidget(QLabel(f"Age: {patient[3]}y {patient[4]}m"))
        layout.addWidget(QLabel(f"Owner Name: {patient[5]}"))
        layout.addWidget(QLabel(f"Owner Contact: {patient[6]}"))
        layout.addWidget(QLabel(f"Owner Email: {patient[7]}"))

        # Add an OK button to close the dialog
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(details_dialog.accept)
        layout.addWidget(button_box)

        details_dialog.setLayout(layout)
        details_dialog.exec()

    def export_to_csv(self):
        """Export patient data (filtered or all) to a CSV file."""
        # Open a file dialog to select the save location
        default_filename = f"patients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", default_filename, "CSV Files (*.csv)")

        if not file_path:
            return  # User canceled the save operation

        # Fetch data from the table (filtered results or all data)
        row_count = self.patient_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "No Data", "There are no records to export.")
            return

        # Prepare data for export
        data = []
        for row in range(row_count):
            row_data = [self.patient_table.item(row, col).text() for col in range(self.patient_table.columnCount())]
            data.append(row_data)

        # Write to CSV
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                # Write the header
                headers = [self.patient_table.horizontalHeaderItem(col).text() for col in
                           range(self.patient_table.columnCount())]
                writer.writerow(headers)
                # Write the data
                writer.writerows(data)

            # Notify the user
            QMessageBox.information(self, "Export Successful", f"Patient data has been exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"An error occurred during export:\n{str(e)}")

    def search_patients(self):
        """Search for patients based on search term and species filter."""
        search_term = self.search_input.text().strip()
        selected_species = self.species_filter.currentText()
        min_age = self.min_age_filter.value()
        max_age = self.max_age_filter.value()

        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()

        # Base query
        query = ('''SELECT patient_id, name, species, breed,
                       age_years || "y " || age_months || "m" AS age,  
                       owner_name, owner_contact, owner_email FROM patients
                       WHERE 1=1''')
        params = []

        # Add text-based search
        if search_term:
            query += " AND (name LIKE ? OR breed LIKE ? OR owner_name LIKE ?)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern] * 3)

        # Add species filter (case-insensitive)
        if selected_species != "All Species":
            query += " AND lower(species) = ?"
            params.append(selected_species.lower())

        # Add age range filters
        if min_age > 0:
            query += " AND age_years >= ?"
            params.append(min_age)
        if max_age > 0:
            query += " AND age_years < ?"
            params.append(max_age)

        # Execute query and fetch results
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Clear input fields
        self.clear_inputs()

        # Display results in the table
        self.patient_table.setRowCount(0)
        for row_index, row_data in enumerate(rows):
            self.patient_table.insertRow(row_index)
            for col_index, col_data in enumerate(row_data):
                self.patient_table.setItem(row_index, col_index, QTableWidgetItem(str(col_data)))

    def load_patients(self):
        """Load and display all patient records from the database."""
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT patient_id, name, species, breed,
                       age_years || "y " || age_months || "m" AS age,  
                       owner_name, owner_contact, owner_email FROM patients''')
        rows = cursor.fetchall()
        conn.close()

        self.patient_table.setRowCount(0)  # Clear existing rows
        for row_index, row_data in enumerate(rows):
            self.patient_table.insertRow(row_index)
            for col_index, col_data in enumerate(row_data):
                self.patient_table.setItem(row_index, col_index, QTableWidgetItem(str(col_data)))

        # Clear input fields
        self.clear_inputs()

    def load_selected_patient(self):
        """Load selected patient data into the input fields."""
        selected_row = self.patient_table.currentRow()
        if selected_row < 0:
            return

        # Get patient details from the selected row, including the ID
        self.selected_patient_id = int(self.patient_table.item(selected_row, 0).text())
        print("Selected patient ID:", self.selected_patient_id)  # Debugging: Print selected ID

        # Populate input fields
        self.name_input.setText(self.patient_table.item(selected_row, 1).text())
        self.species_input.setText(self.patient_table.item(selected_row, 2).text())
        self.breed_input.setText(self.patient_table.item(selected_row, 3).text())

        # Extract and set age years and months
        age_text = self.patient_table.item(selected_row, 4).text()
        age_years, age_months = age_text.split('y')
        self.age_years_input.setValue(int(age_years.strip()))
        self.age_months_input.setValue(int(age_months.strip('m').strip()))

        self.owner_name_input.setText(self.patient_table.item(selected_row, 5).text())
        self.owner_contact_input.setText(self.patient_table.item(selected_row, 6).text())
        self.owner_email_input.setText(self.patient_table.item(selected_row, 7).text())

        # Enable the edit, delete, and view buttons now that a patient is selected
        self.add_button.setEnabled(False)  # Disable the Add button
        self.edit_button.setEnabled(True)  # Enable the Edit button
        self.delete_button.setEnabled(True)  # Enable the Delete button
        self.view_button.setEnabled(True)  # Enable the View Details button
        self.schedule_appointment_button.setEnabled(True)  # Enable Schedule Appointment button


    def navigate_to_appointment_scheduling(self):
        """Emit signal with selected patient's details."""
        if not self.selected_patient_id:
            QMessageBox.warning(self, "No Patient Selected", "Please select a patient to schedule an appointment.")
            return

        patient_name = self.name_input.text()
        self.patient_selected.emit(self.selected_patient_id, patient_name)

        # Clear input fields
        self.clear_inputs()

    def clear_inputs(self):
        """Clear all input fields and reset selected_patient_id."""
        self.name_input.clear()
        self.species_input.clear()
        self.breed_input.clear()
        self.age_years_input.setValue(0)
        self.age_months_input.setValue(0)
        self.owner_name_input.clear()
        self.owner_contact_input.clear()
        self.owner_email_input.clear()
        self.selected_patient_id = None  # Reset selected patient
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.view_button.setEnabled(False)
        self.schedule_appointment_button.setEnabled(False)
        self.add_button.setEnabled(True)  # Ensure Add button remains enabled

