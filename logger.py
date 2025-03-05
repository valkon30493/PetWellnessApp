import logging
import sqlite3
import os

# Set up logging to a file
LOG_FILE = "vet_management_errors.log"
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

# Ensure the error log table exists in the database
def setup_error_logging():
    conn = sqlite3.connect("vet_management.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            error_message TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Call setup function at the start
setup_error_logging()

def log_error(error_message):
    """Log errors to both a file and the database for debugging."""
    logging.error(error_message)

    conn = sqlite3.connect("vet_management.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO error_logs (timestamp, error_message) VALUES (datetime('now'), ?)", (error_message,))
    conn.commit()
    conn.close()
