# app_launcher.py
import sys
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox
from login_screen import LoginWindow
from main_window import MainWindow
from logger import log_error

def launch_app():
    app = QApplication(sys.argv)

    # Load styles
    try:
        with open("style.qss.txt", "r") as style_file:
            app.setStyleSheet(style_file.read())
    except FileNotFoundError:
        print("Style file not found. Running without styles.")

    # Instantiate screens
    login_window = LoginWindow()
    main_window = MainWindow()

    def on_logged_in(username, role):
        main_window.set_user_context(username, role)  # ✅ correct
        main_window.showFullScreen()

    login_window.login_successful.connect(on_logged_in)

    try:
        login_window.show()
        sys.exit(app.exec())
    except Exception:
        err_trace = traceback.format_exc()
        print(err_trace)
        log_error(f"Application startup error:\n{err_trace}")
        QMessageBox.critical(
            login_window,
            "Startup Error",
            "An unexpected error occurred while launching the application.\n"
            "Please check the logs or console for details."
        )
        sys.exit(1)

if __name__ == "__main__":
    launch_app()
