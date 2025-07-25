import sys
import traceback
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QStackedWidget, QPushButton, QMessageBox
)
from patient_management import PatientManagementScreen
from appointment_scheduling import AppointmentSchedulingScreen
from notifications_reminders import NotificationsRemindersScreen
from daily_appointments_calendar import DailyAppointmentsCalendar
from billing_invoicing import BillingInvoicingScreen
from error_log_viewer import ErrorLogViewer
from logger import log_error
from user_management import UserManagementScreen
from user_password_dialog import ChangeMyPasswordDialog

# Inventory import with fallback
try:
    from inventory_management import InventoryManagementScreen
except Exception as e:
    log_error(f"Inventory import failed: {e}")
    class InventoryManagementScreen(QLabel):
        def __init__(self):
            super().__init__("⚠️ Inventory module failed to load")

# Prescription import with fallback
try:
    from prescription_management import PrescriptionManagementScreen
except Exception as e:
    log_error(f"Prescription import failed: {e}")
    class PrescriptionManagementScreen(QLabel):
        def __init__(self):
            super().__init__("⚠️ Prescription module failed to load")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Veterinary Management System")
        self.setGeometry(100, 100, 1600, 900)

        self.user_role = "Guest"
        self.logged_in_username = None

        # Sidebar buttons
        self.patient_button      = QPushButton("Patient Management")
        self.appointment_button  = QPushButton("Appointment Scheduling")
        self.billing_button      = QPushButton("Billing & Invoicing")
        self.inventory_button    = QPushButton("Inventory Management")
        self.prescription_button = QPushButton("Prescription Management")
        self.notifications_button= QPushButton("Notifications & Reminders")
        self.basic_reports_button= QPushButton("Reports")
        self.analytics_button    = QPushButton("Analytics & Reports")
        self.user_mgmt_button    = QPushButton("User Management")
        self.my_account_button   = QPushButton("My Account")
        self.error_log_button    = QPushButton("View Error Logs")
        self.fullscreen_button   = QPushButton("Exit Full Screen")

        # Connect buttons
        self.patient_button.clicked.connect(lambda: self.display_screen(0))
        self.appointment_button.clicked.connect(lambda: self.display_screen(1))
        self.billing_button.clicked.connect(lambda: self.display_screen(2))
        self.inventory_button.clicked.connect(lambda: self.display_screen(3))
        self.prescription_button.clicked.connect(lambda: self.display_screen(4))
        self.notifications_button.clicked.connect(lambda: self.display_screen(5))
        self.basic_reports_button.clicked.connect(lambda: self.display_screen(6))
        self.analytics_button.clicked.connect(lambda: self.display_screen(7))
        self.user_mgmt_button.clicked.connect(lambda: self.display_screen(8))
        self.my_account_button.clicked.connect(self.open_account_settings)
        self.error_log_button.clicked.connect(self.open_error_logs)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)

        # Sidebar layout
        sidebar_layout = QVBoxLayout()
        for w in (
            self.patient_button, self.appointment_button, self.billing_button,
            self.inventory_button, self.prescription_button,
            self.notifications_button, self.basic_reports_button,
            self.analytics_button, self.user_mgmt_button, self.my_account_button
        ):
            sidebar_layout.addWidget(w)
        sidebar_layout.addStretch(1)
        sidebar_layout.addWidget(self.error_log_button)
        sidebar_layout.addWidget(self.fullscreen_button)

        # Screens
        self.patient_screen      = PatientManagementScreen()
        self.appointment_screen  = AppointmentSchedulingScreen()
        self.billing_screen      = BillingInvoicingScreen()
        self.inventory_screen    = InventoryManagementScreen()
        self.prescription_screen = PrescriptionManagementScreen()
        self.notifications_screen= NotificationsRemindersScreen()
        self.reports_screen      = QLabel("Reports Screen")
        self.analytics_screen    = QLabel("Analytics & Reports Screen")
        self.user_mgmt_screen    = UserManagementScreen()

        # Cross-screen connections
        self.patient_screen.patient_list_updated.connect(self.appointment_screen.reload_patients)
        self.patient_screen.patient_selected.connect(self.appointment_screen.load_patient_details)
        self.patient_screen.patient_selected.connect(self.handle_patient_selected)
        self.appointment_screen.reminders_list_updated.connect(self.notifications_screen.reload_reminders)
        self.appointment_screen.navigate_to_billing_signal.connect(self.navigate_to_billing_screen)
        self.billing_screen.invoiceSelected.connect(self.notifications_screen.load_reminders)

        # Stacked widget
        self.stacked = QStackedWidget()
        for screen in (
            self.patient_screen, self.appointment_screen, self.billing_screen,
            self.inventory_screen, self.prescription_screen, self.notifications_screen,
            self.reports_screen, self.analytics_screen, self.user_mgmt_screen
        ):
            self.stacked.addWidget(screen)

        # Calendar
        self.calendar_widget = DailyAppointmentsCalendar()

        # Main layout
        main_layout = QHBoxLayout()
        sidebar_plus_cal = QVBoxLayout()
        sidebar_plus_cal.addWidget(self.calendar_widget, 2)
        sidebar_plus_cal.addLayout(sidebar_layout, 3)

        main_layout.addLayout(sidebar_plus_cal, 2)
        main_layout.addWidget(self.stacked, 5)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def display_screen(self, idx):
        self.stacked.setCurrentIndex(idx)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.showNormal()

    def open_error_logs(self):
        ErrorLogViewer().exec()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self.fullscreen_button.setText(
            "Exit Full Screen" if self.isFullScreen() else "Full Screen"
        )

    def handle_patient_selected(self, pid, pname):
        self.appointment_screen.load_patient_details(pid, pname)
        self.display_screen(1)

    def navigate_to_billing_screen(self, appt_id):
        self.billing_screen.load_invoice_details(appt_id)
        self.display_screen(2)

    def set_user_context(self, username, role):
        self.logged_in_username = username
        self.user_role = role
        self.adjust_ui_for_role()

    def adjust_ui_for_role(self):
        role = self.user_role.lower()

        if role == "admin":
            self.user_mgmt_button.setEnabled(True)
            return

        if role == "veterinarian":
            self.billing_button.setEnabled(False)
            self.inventory_button.setEnabled(False)
            self.analytics_button.setEnabled(False)
            self.basic_reports_button.setEnabled(False)
            self.user_mgmt_button.setEnabled(False)

        if role == "receptionist":
            self.prescription_button.setEnabled(False)
            self.inventory_button.setEnabled(False)
            self.analytics_button.setEnabled(False)
            self.basic_reports_button.setEnabled(False)
            self.user_mgmt_button.setEnabled(False)

    def open_account_settings(self):
        if not self.logged_in_username:
            QMessageBox.warning(self, "Error", "No logged-in user.")
            return
        dlg = ChangeMyPasswordDialog(self.logged_in_username)
        dlg.exec()
