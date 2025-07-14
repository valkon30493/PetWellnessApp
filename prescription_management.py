# prescription_management.py

import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit,
    QPlainTextEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt

DB = "vet_management.db"

def get_all_prescriptions():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT pr.prescription_id,
               p.name AS patient_name,
               pr.medication,
               pr.dosage,
               pr.instructions,
               pr.date_issued
          FROM prescriptions pr
          JOIN patients p ON pr.patient_id = p.patient_id
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def create_prescription(patient_id, medication, dosage, instructions):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO prescriptions
          (patient_id, medication, dosage, instructions, date_issued)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (patient_id, medication, dosage, instructions))
    conn.commit()
    conn.close()

def update_prescription(prescription_id, **fields):
    cols, vals = zip(*fields.items())
    set_clause = ", ".join(f"{col}=?" for col in cols)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE prescriptions
           SET {set_clause}
         WHERE prescription_id=?
    """, (*vals, prescription_id))
    conn.commit()
    conn.close()

def delete_prescription(prescription_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM prescriptions WHERE prescription_id=?", (prescription_id,))
    conn.commit()
    conn.close()

class PrescriptionManagementScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prescription Management")
        self.selected_prescription_id = None

        main = QVBoxLayout(self)

        # ── Table ───────────────────────────────────
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID","Patient","Medication","Dosage","Instructions","Date Issued"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.on_select)
        main.addWidget(self.table)

        # ── Form ────────────────────────────────────
        form = QFormLayout()
        # patient dropdown
        self.patient_combo = QComboBox()
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT patient_id, name FROM patients")
        for pid, name in cur.fetchall():
            self.patient_combo.addItem(f"{name} (ID:{pid})", pid)
        conn.close()

        self.med_input   = QLineEdit()
        self.dosage_input = QLineEdit()
        self.instr_input  = QPlainTextEdit()
        form.addRow("Patient:", self.patient_combo)
        form.addRow("Medication:", self.med_input)
        form.addRow("Dosage:", self.dosage_input)
        form.addRow("Instructions:", self.instr_input)
        main.addLayout(form)

        # ── Buttons ─────────────────────────────────
        btns = QHBoxLayout()
        self.new_btn    = QPushButton("New")
        self.save_btn   = QPushButton("Save")
        self.delete_btn = QPushButton("Delete")
        for b in (self.new_btn, self.save_btn, self.delete_btn):
            btns.addWidget(b)
        main.addLayout(btns)

        # ── Signals ─────────────────────────────────
        self.new_btn.clicked.connect(self.on_new)
        self.save_btn.clicked.connect(self.on_save)
        self.delete_btn.clicked.connect(self.on_delete)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for pr in get_all_prescriptions():
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, v in enumerate(pr):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))

    def on_select(self):
        r = self.table.currentRow()
        if r < 0:
            return
        self.selected_prescription_id = int(self.table.item(r, 0).text())
        pid = int(self.table.item(r, 1).text().split("ID:")[1].rstrip(")"))
        idx = self.patient_combo.findData(pid)
        if idx >= 0:
            self.patient_combo.setCurrentIndex(idx)
        self.med_input.setText(self.table.item(r, 2).text())
        self.dosage_input.setText(self.table.item(r, 3).text())
        self.instr_input.setPlainText(self.table.item(r, 4).text())

    def on_new(self):
        self.selected_prescription_id = None
        self.patient_combo.setCurrentIndex(0)
        self.med_input.clear()
        self.dosage_input.clear()
        self.instr_input.clear()

    def on_save(self):
        med = self.med_input.text().strip()
        dosage = self.dosage_input.text().strip()
        instr = self.instr_input.toPlainText().strip()
        pid = self.patient_combo.currentData()
        if not med or not dosage:
            QMessageBox.warning(self, "Input Error", "Medication and dosage required.")
            return
        if self.selected_prescription_id:
            update_prescription(
                self.selected_prescription_id,
                medication=med, dosage=dosage, instructions=instr
            )
        else:
            create_prescription(pid, med, dosage, instr)
        self.refresh()
        self.on_new()

    def on_delete(self):
        if not self.selected_prescription_id:
            return
        if QMessageBox.question(self, "Confirm", "Delete this prescription?") != QMessageBox.Yes:
            return
        delete_prescription(self.selected_prescription_id)
        self.refresh()
        self.on_new()
