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

# ── Add duration_minutes if missing ──────────────────────────────────
try:
    cursor.execute("""
      ALTER TABLE appointments
        ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 30
    """)
except sqlite3.OperationalError:
    # column already exists
    pass

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

# ── Add VAT / Discount columns if missing ──────────────────────────
for col, definition in [
    ("vat_pct",        "REAL NOT NULL DEFAULT 0"),
    ("vat_amount",     "REAL NOT NULL DEFAULT 0"),
    ("vat_flag",       "TEXT NOT NULL DEFAULT ''"),
    ("discount_pct",   "REAL NOT NULL DEFAULT 0"),
    ("discount_amount","REAL NOT NULL DEFAULT 0")
]:
    try:
        cursor.execute(f"""
          ALTER TABLE invoice_items
            ADD COLUMN {col} {definition}
        """)
    except sqlite3.OperationalError:
        # column already exists
        pass

# ── INVENTORY ────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS items (
  item_id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name               TEXT    NOT NULL,
  description        TEXT,
  unit_cost          REAL    NOT NULL DEFAULT 0,
  unit_price         REAL    NOT NULL DEFAULT 0,
  reorder_threshold  INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stock_movements (
  movement_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id      INTEGER NOT NULL REFERENCES items(item_id),
  change_qty   INTEGER NOT NULL,
  reason       TEXT,
  timestamp    TEXT    NOT NULL
)
""")

# ── PRESCRIPTIONS ───────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS prescriptions (
  prescription_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id       INTEGER NOT NULL REFERENCES patients(patient_id),
  medication       TEXT    NOT NULL,
  dosage           TEXT    NOT NULL,
  instructions     TEXT,
  date_issued      TEXT    NOT NULL
)
""")

# add status column
try:
    cursor.execute("ALTER TABLE prescriptions ADD COLUMN status TEXT NOT NULL DEFAULT 'New'")
except sqlite3.OperationalError:
    pass  # already added

# audit trail
cursor.execute("""
CREATE TABLE IF NOT EXISTS prescription_history (
    history_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id  INTEGER NOT NULL REFERENCES prescriptions(prescription_id),
    user_id          INTEGER,             -- if you have user login
    action           TEXT    NOT NULL,
    timestamp        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changes_json     TEXT
)
""")

# --- Medical Records (SOAP) ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS medical_records (
    record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     INTEGER NOT NULL REFERENCES patients(patient_id),
    appointment_id INTEGER     REFERENCES appointments(appointment_id),
    date_created   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vet_name       TEXT,
    chief_complaint TEXT,
    subjective     TEXT,
    objective      TEXT,
    assessment     TEXT,
    plan           TEXT,
    diagnosis      TEXT,
    vitals_json    TEXT,       -- optional JSON blob for T°, HR, RR, Wt, etc.
    follow_up_date TEXT
)
""")

# Attachments linked to a record (x-rays, pdfs, images)
cursor.execute("""
CREATE TABLE IF NOT EXISTS record_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id     INTEGER NOT NULL REFERENCES medical_records(record_id) ON DELETE CASCADE,
    file_name     TEXT    NOT NULL,
    file_path     TEXT    NOT NULL,
    mime_type     TEXT,
    uploaded_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""")

# Consent documents (signed scans/photos/PDFs), optionally linked to appointment
cursor.execute("""
CREATE TABLE IF NOT EXISTS consents (
    consent_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     INTEGER NOT NULL REFERENCES patients(patient_id),
    appointment_id INTEGER REFERENCES appointments(appointment_id),
    consent_type   TEXT NOT NULL,        -- e.g., Surgery, Anaesthesia, Dental, Imaging
    notes          TEXT,
    file_name      TEXT,                 -- optional stored scan
    file_path      TEXT,
    date_signed    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""")

# --- Consents Table ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS consents (
    consent_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     INTEGER NOT NULL REFERENCES patients(patient_id),
    consent_type   TEXT    NOT NULL,        -- Surgery / Anesthesia / Procedure / Media / Other
    notes          TEXT,
    signer_name    TEXT,
    signed_on      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until    TEXT,
    file_path      TEXT                      -- optional: saved PDF/scanned file
)
""")

# ── CONSENT FORMS ─────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS consent_templates (
  template_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  body_text     TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS consent_forms (
  consent_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id      INTEGER NOT NULL REFERENCES patients(patient_id),
  template_id     INTEGER,                          -- optional; snapshot kept in body_text
  form_type       TEXT NOT NULL,                    -- e.g., "Surgery Consent"
  body_text       TEXT NOT NULL,                    -- snapshot at time of creation
  signed_by       TEXT,                             -- person who signed (owner/guardian)
  relation        TEXT,                             -- Owner / Guardian / Other
  signature_path  TEXT,                             -- optional: stored PNG/JPG path
  status          TEXT NOT NULL DEFAULT 'Draft',    -- Draft | Signed | Voided
  follow_up_date  TEXT,                             -- optional next check date
  created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""")

# Optional starter templates
cursor.execute("INSERT OR IGNORE INTO consent_templates (name, body_text) VALUES (?, ?)",
               ("General Treatment Consent",
                "I, {owner_name}, consent to examination and treatment for {patient_name}..."))
cursor.execute("INSERT OR IGNORE INTO consent_templates (name, body_text) VALUES (?, ?)",
               ("Surgery Consent",
                "I, {owner_name}, authorize surgical procedure for {patient_name} on {date}..."))


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
        cursor.execute(
            'INSERT OR IGNORE INTO users (username, password, role_id) VALUES (?, ?, ?)',
            (username, hashed_password, role_id)
        )

create_user('admin', 'admin123', 'Admin')
create_user('vetuser', 'vet123', 'Veterinarian')
create_user('reception', 'recep123', 'Receptionist')


# --- Commit & Close ---
conn.commit()
conn.close()
