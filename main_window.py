import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QStackedWidget,
                               QPushButton)
from patient_management import PatientManagementScreen
from appointment_scheduling import AppointmentSchedulingScreen
from notifications_reminders import NotificationsRemindersScreen
from daily_appointments_calendar import DailyAppointmentsCalendar  # Import the Daily Appointments Calendar
from billing_invoicing import BillingInvoicingScreen
from error_log_viewer import ErrorLogViewer  # Import the log viewer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Veterinary Management System")
        self.setGeometry(100, 100, 1600, 900)  # Adjusted width to accommodate calendar

        # Sidebar buttons
        self.patient_button = QPushButton("Patient Management")
        self.appointment_button = QPushButton("Appointment Scheduling")
        self.billing_button = QPushButton("Billing and Invoicing")
        self.inventory_button = QPushButton("Inventory Management")
        self.prescription_button = QPushButton("Prescription Management")
        self.notifications_button = QPushButton("Notifications & Reminders")
        self.basic_reports_button = QPushButton("Reports")
        self.analytics_button = QPushButton("Analytics & Reports")
        self.error_log_button = QPushButton("View Error Logs")
        self.fullscreen_button = QPushButton("Exit Full Screen")

        # Connect buttons to screen switching
        self.patient_button.clicked.connect(lambda: self.display_screen(0))
        self.appointment_button.clicked.connect(lambda: self.display_screen(1))
        self.billing_button.clicked.connect(lambda: self.display_screen(2))
        self.inventory_button.clicked.connect(lambda: self.display_screen(3))
        self.prescription_button.clicked.connect(lambda: self.display_screen(4))
        self.notifications_button.clicked.connect(lambda: self.display_screen(5))
        self.basic_reports_button.clicked.connect(lambda: self.display_screen(6))
        self.analytics_button.clicked.connect(lambda: self.display_screen(7))
        self.error_log_button.clicked.connect(self.open_error_logs)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

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
        sidebar_layout.addWidget(self.error_log_button)
        sidebar_layout.addWidget(self.fullscreen_button)


        # Create widgets for each section
        self.patient_screen = PatientManagementScreen()
        self.appointment_screen = AppointmentSchedulingScreen()
        self.billing_screen = BillingInvoicingScreen()
        self.inventory_screen = QLabel("Inventory Management Screen")
        self.prescription_screen = QLabel("Prescription Management Screen")
        self.notifications_screen = NotificationsRemindersScreen()
        self.reports_screen = QLabel("Reports Screen")
        self.analytics_screen = QLabel("Analytics & Reports Screen")

        # Connect signals
        self.patient_screen.patient_list_updated.connect(self.appointment_screen.reload_patients)
        self.appointment_screen.reminders_list_updated.connect(self.notifications_screen.reload_reminders)
        self.patient_screen.patient_selected.connect(self.appointment_screen.load_patient_details)
        self.patient_screen.patient_selected.connect(self.handle_patient_selected)
        self.appointment_screen.navigate_to_billing_signal.connect(self.navigate_to_billing_screen)

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

        # Add the calendar widget
        self.calendar_widget = DailyAppointmentsCalendar()

        # Layout for the main window
        main_layout = QHBoxLayout()

        # Calendar section (always visible)
        calendar_section = QVBoxLayout()
        calendar_section.addWidget(self.calendar_widget)

        # Combine calendar and sidebar in a single layout
        sidebar_and_calendar = QVBoxLayout()
        sidebar_and_calendar.addLayout(calendar_section)
        sidebar_and_calendar.addLayout(sidebar_layout)

        main_layout.addLayout(sidebar_and_calendar, 2)  # 2/5 of the space for sidebar + calendar
        main_layout.addWidget(self.stacked_widget, 5)  # 3/5 of the space for the screens

        # Set central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def display_screen(self, index):
        """Switch to the selected screen."""
        self.stacked_widget.setCurrentIndex(index)

    def keyPressEvent(self, event):
        """Exit full-screen mode when the Escape key is pressed."""
        if event.key() == Qt.Key_Escape:
            self.showNormal()  # Exit full-screen mode and return to normal window

    def open_error_logs(self):
        """Open the error log viewer dialog."""
        dialog = ErrorLogViewer()
        dialog.exec()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()

        else:
            self.showFullScreen()
        self.update_fullscreen_button_text()  # Update button text after toggling

    def handle_patient_selected(self, patient_id, patient_name):
        """Handle navigation to Appointment Scheduling with pre-filled patient details."""
        self.appointment_screen.load_patient_details(patient_id, patient_name)
        self.display_screen(1)  # Switch to Appointment Scheduling screen

    def navigate_to_billing_screen(self, appointment_id):
        """Switch to the Billing and Invoicing screen and populate with appointment details."""
        self.billing_screen.load_invoice_details(appointment_id)
        self.display_screen(2)  # Assuming the Billing and Invoicing screen is at index 2

    def update_fullscreen_button_text(self):
        """Update button text based on full-screen state."""
        if self.isFullScreen():
            self.fullscreen_button.setText("Exit Full Screen")
        else:
            self.fullscreen_button.setText("Full Screen")

# Run the application
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        # Load the QSS file
        try:
            with open("style.qss.txt", "r") as style_file:
                app.setStyleSheet(style_file.read())
        except FileNotFoundError:
            print("Style file not found. Running without styles.")

        # Create and display the main window
        main_window = MainWindow()
        main_window.showFullScreen()  # Full-screen mode
        sys.exit(app.exec())
    except Exception as e:
        log_error(f"Application startup error: {str(e)}")
