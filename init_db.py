import sqlite3
from hashlib import sha256

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('vet_management.db')
cursor = conn.cursor()

# Create Roles table
cursor.execute('''
CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE
)
''')

# Create Users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,  -- Store the hashed password
    role_id INTEGER,
    FOREIGN KEY (role_id) REFERENCES roles (role_id)
)
''')

# Create Patients table
cursor.execute('''
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT,
    age INTEGER,
    owner_name TEXT NOT NULL,
    owner_contact TEXT
)
''')
# Add the new column for age_years if it doesn't already exist
try:
    cursor.execute("ALTER TABLE patients ADD COLUMN age_years INTEGER DEFAULT 0")
    print("Added age_years column to patients table.")
except sqlite3.OperationalError:
    print("Column age_years already exists.")

# Add the new column for age_months if it doesn't already exist
try:
    cursor.execute("ALTER TABLE patients ADD COLUMN age_months INTEGER DEFAULT 0")
    print("Added age_months column to patients table.")
except sqlite3.OperationalError:
    print("Column age_months already exists.")

# Add the new column for owner email if it doesn't already exist
try:
    cursor.execute("ALTER TABLE patients ADD COLUMN owner_email TEXT")
    print("Added owner_email column to patients table.")
except sqlite3.OperationalError:
    print("Column owner_email already exists.")

# Delete the old column for age if it already exists
try:
    cursor.execute("ALTER TABLE patients DELETE COLUMN age INTEGER")
    print("Deleted age column from patients table.")
except sqlite3.OperationalError:
    print("Column age already deleted.")

# Create Appointments table
cursor.execute('''
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    date_time TEXT NOT NULL,
    reason TEXT NOT NULL,
    veterinarian TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
)
''')
try:
    cursor.execute("ALTER TABLE appointments ADD COLUMN notification_status TEXT DEFAULT 'Not Sent'")
    print("Added notification_status column to patients table.")
except sqlite3.OperationalError:
    print("Column notification_status already exists.")

try:
    cursor.execute("ALTER TABLE appointments ADD COLUMN appointment_type TEXT DEFAULT 'General'")
    print("Added appointment_type column to appointments table.")
except sqlite3.OperationalError:
    print("Column appointment_type already exists.")

# Create Reminders table
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER,
    reminder_time DATETIME NOT NULL,
    reminder_status TEXT DEFAULT 'Pending',
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
)
''')

try:
    cursor.execute("ALTER TABLE reminders ADD COLUMN reminder_reason TEXT")
    print("Added reminder_reason column to reminders table.")
except sqlite3.OperationalError:
    print("Column reminder_reason already exists.")

#Create Invoices Table
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
    FOREIGN KEY (appointment_id) REFERENCES appointments (appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
)
''')

try:
    cursor.execute("ALTER TABLE invoices ADD COLUMN remaining_balance REAL DEFAULT 0")
    print("Added remaining_balance column to invoices table.")
except sqlite3.OperationalError:
    print("Column remaining_balance already exists.")


try:
    cursor.execute("ALTER TABLE invoices ADD COLUMN latest_payment_method TEXT DEFAULT NULL")
    print("Added latest_payment_method column to invoices table.")
except sqlite3.OperationalError:
    print("Column latest_payment_method already exists.")



#Create Payments Table
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

#Create Invoice Items Table
cursor.execute('''
CREATE TABLE IF NOT EXISTS invoice_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER,
    item_name TEXT,
    quantity INTEGER,
    unit_price REAL,
    total REAL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
)
''')

try:
    cursor.execute("ALTER TABLE invoice_items ADD COLUMN item_name TEXT")
    print("Added item_name column to invoice items table.")
except sqlite3.OperationalError:
    print("Column item_name already exists.")

try:
    cursor.execute("ALTER TABLE invoice_items ADD COLUMN total REAL")
    print("Added total column to invoice items table.")
except sqlite3.OperationalError:
    print("Column total already exists.")

# Insert default roles
roles = ['Admin', 'Veterinarian', 'Receptionist']
for role in roles:
    cursor.execute('INSERT OR IGNORE INTO roles (role_name) VALUES (?)', (role,))

# Function to create a sample user with hashed password
def create_user(username, password, role_name):
    # Hash the password for security
    hashed_password = sha256(password.encode()).hexdigest()

    # Get role_id for the role
    cursor.execute('SELECT role_id FROM roles WHERE role_name = ?', (role_name,))
    role = cursor.fetchone()
    if role:
        role_id = role[0]
        # Insert user into the users table
        cursor.execute('INSERT OR IGNORE INTO users (username, password, role_id) VALUES (?, ?, ?)',
                       (username, hashed_password, role_id))
    else:
        print("Role not found")

# Create a sample admin user
create_user('admin', 'admin123', 'Admin')

# Commit changes and close the connection
conn.commit()
conn.close()
