import sqlite3, json
DB = "vet_management.db"

def log_history(prescription_id, action, changes=None, user_id=None):
    conn = sqlite3.connect(DB)
    cur  = conn.cursor()
    cur.execute("""
      INSERT INTO prescription_history
        (prescription_id, user_id, action, changes_json)
      VALUES (?, ?, ?, ?)
    """, (
        prescription_id,
        user_id,
        action,
        json.dumps(changes) if changes else None
    ))
    conn.commit()
    conn.close()
