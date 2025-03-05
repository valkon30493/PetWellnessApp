import sys
import csv
from datetime import datetime
import sqlite3
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
                               QPushButton, QFormLayout, QTableWidget, QTableWidgetItem, QStackedWidget, QMessageBox,
                               QSpinBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog)
from patient_management import PatientManagementScreen  # Import the Patient Management screen

class PatientManagementScreen(QWidget):
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
        self.name_input = QLineEdit()
        self.species_input = QLineEdit()
        self.breed_input = QLineEdit()
        self.age_input = QLineEdit()
        self.owner_name_input = QLineEdit()
        self.owner_contact_input = QLineEdit()

        # Add fields to form layout
        form_layout.addRow("Patient Name:", self.name_input)
        form_layout.addRow("Species:", self.species_input)
        form_layout.addRow("Breed:", self.breed_input)
        form_layout.addRow("Age:", self.age_input)
        form_layout.addRow("Owner Name:", self.owner_name_input)
        form_layout.addRow("Owner Contact:", self.owner_contact_input)

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
        self.view_button.clicked.connect(self.view_details)  # Connect to view details functionality

        # View All Patients button
        view_button = QPushButton("View All")
        view_button.clicked.connect(self.load_patients)

        # Export to CSV button
        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.export_to_csv)

        # Add buttons to layout
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.view_button)  # View Details button here
        button_layout.addWidget(view_button)        # View All button here
        button_layout.addWidget(export_button)

        # Table to display patient records
        self.patient_table = QTableWidget()
        self.patient_table.setColumnCount(7)  # Include ID column
        self.patient_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Species", "Breed", "Age", "Owner Name", "Owner Contact"])
        self.patient_table.itemSelectionChanged.connect(self.load_selected_patient)

        # Add layouts to main layout
        layout.addLayout(search_layout)  # Add search bar at the top
        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.patient_table)

        self.setLayout(layout)

        # Track the selected patient's ID for editing
        self.selected_patient_id = None

    def add_patient(self):
        """Insert new patient data into the database."""
        # Retrieve data from input fields
        name = self.name_input.text()
        species = self.species_input.text()
        breed = self.breed_input.text()
        age = self.age_input.text()
        owner_name = self.owner_name_input.text()
        owner_contact = self.owner_contact_input.text()

        # Ensure required fields are filled out
        if not (name and species and owner_name):
            QMessageBox.warning(self, "Input Error", "Please fill out all required fields.")
            return

        # Insert new patient record
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO patients (name, species, breed, age, owner_name, owner_contact)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, species, breed, age, owner_name, owner_contact))
        conn.commit()
        conn.close()

        # Clear input fields and refresh table
        self.clear_inputs()
        self.load_patients()

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
        age = self.age_input.text()
        owner_name = self.owner_name_input.text()
        owner_contact = self.owner_contact_input.text()

        # Update the patient's information in the database
        conn = sqlite3.connect('vet_management.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE patients
            SET name = ?, species = ?, breed = ?, age = ?, owner_name = ?, owner_contact = ?
            WHERE patient_id = ?
        ''', (name, species, breed, age, owner_name, owner_contact, self.selected_patient_id))
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
            SELECT name, species, breed, age, owner_name, owner_contact
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
        layout.addWidget(QLabel(f"Age: {patient[3]}"))
        layout.addWidget(QLabel(f"Owner Name: {patient[4]}"))
        layout.addWidget(QLabel(f"Owner Contact: {patient[5]}"))

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
        query = "SELECT patient_id, name, species, breed, age, owner_name, owner_contact FROM patients WHERE 1=1"
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
            query += " AND age >= ?"
            params.append(min_age)
        if max_age > 0:
            query += " AND age <= ?"
            params.append(max_age)

        # Execute query and fetch results
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

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
        cursor.execute("SELECT patient_id, name, species, breed, age, owner_name, owner_contact FROM patients")
        rows = cursor.fetchall()
        conn.close()

        self.patient_table.setRowCount(0)  # Clear existing rows
        for row_index, row_data in enumerate(rows):
            self.patient_table.insertRow(row_index)
            for col_index, col_data in enumerate(row_data):
                self.patient_table.setItem(row_index, col_index, QTableWidgetItem(str(col_data)))

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
        self.age_input.setText(self.patient_table.item(selected_row, 4).text())
        self.owner_name_input.setText(self.patient_table.item(selected_row, 5).text())
        self.owner_contact_input.setText(self.patient_table.item(selected_row, 6).text())

        # Enable the edit, delete, and view buttons now that a patient is selected
        self.edit_button.setEnabled(True)  # Enable the Edit button
        self.delete_button.setEnabled(True)  # Enable the Delete button
        self.view_button.setEnabled(True)  # Enable the View Details button

    def clear_inputs(self):
        """Clear all input fields and reset selected_patient_id."""
        self.name_input.clear()
        self.species_input.clear()
        self.breed_input.clear()
        self.age_input.clear()
        self.owner_name_input.clear()
        self.owner_contact_input.clear()
        self.selected_patient_id = None
        """self.edit_button.setEnabled(False)  # Disable edit button when inputs are cleared"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Veterinary Management System")
        self.setGeometry(200, 200, 1000, 600)


        # Left sidebar with buttons
        self.patient_button = QPushButton("Patient Management")
        self.appointment_button = QPushButton("Appointment Scheduling")
        self.billing_button = QPushButton("Billing and Invoicing")
        self.inventory_button = QPushButton("Inventory Management")
        self.prescription_button = QPushButton("Prescription Management")
        self.notifications_button = QPushButton("Notifications & Reminders")
        self.basic_reports_button = QPushButton("Reports")
        self.analytics_button = QPushButton("Analytics & Reports")

        # Connect buttons to functions to switch views
        self.patient_button.clicked.connect(lambda: self.display_screen(0))
        self.appointment_button.clicked.connect(lambda: self.display_screen(1))
        self.billing_button.clicked.connect(lambda: self.display_screen(2))
        self.inventory_button.clicked.connect(lambda: self.display_screen(3))
        self.prescription_button.clicked.connect(lambda: self.display_screen(4))
        self.notifications_button.clicked.connect(lambda: self.display_screen(5))
        self.basic_reports_button.clicked.connect(lambda: self.display_screen(6))
        self.analytics_button.clicked.connect(lambda: self.display_screen(7))

        # Sidebar layout
        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(self.patient_button)
        sidebar_layout.addWidget(self.appointment_button)
        sidebar_layout.addWidget(self.billing_button)
        sidebar_layout.addWidget(self.inventory_button)
        sidebar_layout.addWidget(self.prescription_button)
        sidebar_layout.addWidget(self.notifications_button)
        sidebar_layout.addWidget(self.basic_reports_button)
        sidebar_layout.addWidget(self.analytics_button)
        sidebar_layout.addStretch(1)

        # Create widgets for each section
        self.patient_screen = PatientManagementScreen()
        self.appointment_screen = QLabel("Appointment Scheduling Screen")
        self.billing_screen = QLabel("Billing and Invoicing Screen")
        self.inventory_screen = QLabel("Inventory Management Screen")
        self.prescription_screen = QLabel("Prescription Management Screen")
        self.notifications_screen = QLabel("Notifications & Reminders Screen")
        self.reports_screen = QLabel("Reports Screen")
        self.analytics_screen = QLabel("Analytics & Reports Screen")

        # Stacked widget to hold different screens
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.patient_screen)
        self.stacked_widget.addWidget(self.appointment_screen)
        self.stacked_widget.addWidget(self.billing_screen)
        self.stacked_widget.addWidget(self.inventory_screen)
        self.stacked_widget.addWidget(self.prescription_screen)
        self.stacked_widget.addWidget(self.notifications_screen)
        self.stacked_widget.addWidget(self.reports_screen)
        self.stacked_widget.addWidget(self.analytics_screen)

        # Main layout combining sidebar and stacked widget
        main_layout = QHBoxLayout()
        main_layout.addLayout(sidebar_layout, 1)
        main_layout.addWidget(self.stacked_widget, 4)

        # Set the central widget with the main layout
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def display_screen(self, index):
        """Switch to the selected screen in the stacked widget."""
        self.stacked_widget.setCurrentIndex(index)




# Run the application
app = QApplication(sys.argv)
main_window = MainWindow()
main_window.show()
sys.exit(app.exec())
