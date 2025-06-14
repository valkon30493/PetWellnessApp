
import sqlite3
from hashlib import sha256

# Connect to the database
conn = sqlite3.connect('vet_management.db')
cursor = conn.cursor()

# --- Roles Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE
)
''')

# --- Users Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role_id INTEGER,
    FOREIGN KEY (role_id) REFERENCES roles (role_id)
)
''')

# --- Patients Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT,
    age_years INTEGER DEFAULT 0,
    age_months INTEGER DEFAULT 0,
    owner_name TEXT NOT NULL,
    owner_contact TEXT,
    owner_email TEXT
)
''')

# --- Appointments Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    date_time TEXT NOT NULL,
    reason TEXT NOT NULL,
    veterinarian TEXT NOT NULL,
    status TEXT NOT NULL,
    notification_status TEXT DEFAULT 'Not Sent',
    appointment_type TEXT DEFAULT 'General',
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
)
''')

# --- Reminders Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER,
    reminder_time DATETIME NOT NULL,
    reminder_status TEXT DEFAULT 'Pending',
    reminder_reason TEXT,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
)
''')

# --- Invoices Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER,
    patient_id INTEGER,
    total_amount REAL NOT NULL,
    tax REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    final_amount REAL NOT NULL,
    payment_status TEXT CHECK(payment_status IN ('Paid', 'Unpaid', 'Partially Paid')) DEFAULT 'Unpaid',
    payment_method TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    remaining_balance REAL DEFAULT 0,
    FOREIGN KEY (appointment_id) REFERENCES appointments (appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
)
''')

# --- Payment History Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS payment_history (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    amount_paid REAL NOT NULL,
    payment_method TEXT,
    notes TEXT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id) ON DELETE CASCADE
)
''')

# --- Invoice Items Table ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS invoice_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
)
''')


# --- Insert Default Roles ---
roles = ['Admin', 'Veterinarian', 'Receptionist']
for role in roles:
    cursor.execute('INSERT OR IGNORE INTO roles (role_name) VALUES (?)', (role,))

# --- Create Default Admin User ---
def create_user(username, password, role_name):
    hashed_password = sha256(password.encode()).hexdigest()
    cursor.execute('SELECT role_id FROM roles WHERE role_name = ?', (role_name,))
    role = cursor.fetchone()
    if role:
        role_id = role[0]
        cursor.execute('INSERT OR IGNORE INTO users (username, password, role_id) VALUES (?, ?, ?)',
                       (username, hashed_password, role_id))

create_user('admin', 'admin123', 'Admin')

# --- Commit & Close ---
conn.commit()
conn.close()
