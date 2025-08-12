# medical_records.py
import os, shutil, json, sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPlainTextEdit, QComboBox, QPushButton, QLabel, QFileDialog, QMessageBox,
    QDateEdit, QHeaderView
)
from PySide6.QtCore import Qt, QDate

DB = "vet_management.db"
ATTACH_DIR = "attachments"  # will be created if missing

class MedicalRecordsScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Medical Records")
        self.selected_record_id = None
        os.makedirs(ATTACH_DIR, exist_ok=True)

        main = QVBoxLayout(self)

        # === Filters / Top Bar ===
        top = QHBoxLayout()
        self.patient_filter = QLineEdit(); self.patient_filter.setPlaceholderText("Filter by patient name…")
        self.vet_filter     = QLineEdit(); self.vet_filter.setPlaceholderText("Filter by vet…")
        self.start_date     = QDateEdit(QDate.currentDate().addMonths(-1)); self.start_date.setCalendarPopup(True)
        self.end_date       = QDateEdit(QDate.currentDate()); self.end_date.setCalendarPopup(True)
        refresh = QPushButton("Apply Filters")
        refresh.clicked.connect(self.load_records)

        top.addWidget(QLabel("Patient:")); top.addWidget(self.patient_filter)
        top.addWidget(QLabel("Vet:"));     top.addWidget(self.vet_filter)
        top.addWidget(QLabel("From:"));    top.addWidget(self.start_date)
        top.addWidget(QLabel("To:"));      top.addWidget(self.end_date)
        top.addWidget(refresh)
        main.addLayout(top)

        # === Table ===
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID","Date","Patient","Appointment","Vet","Chief Complaint","Diagnosis","Follow‑Up"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select_row)
        main.addWidget(self.table)

        # === Form ===
        form = QFormLayout()
        self.patient_picker = QComboBox()
        self._load_patient_list()

        self.appt_picker = QComboBox()
        self._reload_appt_list()  # all appts initially; will filter after patient selection
        self.patient_picker.currentIndexChanged.connect(self._reload_appt_list)

        self.vet_input    = QComboBox(); self.vet_input.addItems(["", "Dr. Souzana", "Dr. Klio"])
        self.chief_input  = QLineEdit()
        self.subj_input   = QPlainTextEdit()
        self.obj_input    = QPlainTextEdit()
        self.assess_input = QPlainTextEdit()
        self.plan_input   = QPlainTextEdit()
        self.diag_input   = QLineEdit()
        self.follow_up    = QDateEdit(); self.follow_up.setCalendarPopup(True); self.follow_up.setDate(QDate.currentDate())

        form.addRow("Patient:", self.patient_picker)
        form.addRow("Appointment:", self.appt_picker)
        form.addRow("Veterinarian:", self.vet_input)
        form.addRow("Chief Complaint:", self.chief_input)
        form.addRow("Subjective:", self.subj_input)
        form.addRow("Objective:", self.obj_input)
        form.addRow("Assessment:", self.assess_input)
        form.addRow("Plan:", self.plan_input)
        form.addRow("Diagnosis:", self.diag_input)
        form.addRow("Follow‑Up Date:", self.follow_up)
        main.addLayout(form)

        # === Buttons ===
        btns = QHBoxLayout()
        self.new_btn   = QPushButton("New")
        self.save_btn  = QPushButton("Save")
        self.delete_btn= QPushButton("Delete")
        self.attach_btn= QPushButton("Add Attachment")
        self.view_att_btn = QPushButton("View Attachments…")
        for b in (self.new_btn, self.save_btn, self.delete_btn, self.attach_btn, self.view_att_btn):
            btns.addWidget(b)
        main.addLayout(btns)

        self.new_btn.clicked.connect(self.on_new)
        self.save_btn.clicked.connect(self.on_save)
        self.delete_btn.clicked.connect(self.on_delete)
        self.attach_btn.clicked.connect(self.on_add_attachment)
        self.view_att_btn.clicked.connect(self.on_view_attachments)

        self.on_new()
        self.load_records()

    # ---------- Data helpers ----------
    def _load_patient_list(self):
        self.patient_picker.clear()
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("SELECT patient_id, name FROM patients ORDER BY name")
        for pid, name in cur.fetchall():
            self.patient_picker.addItem(f"{name} (ID:{pid})", pid)
        conn.close()

    def _reload_appt_list(self):
        self.appt_picker.clear()
        pid = self.patient_picker.currentData()
        conn = sqlite3.connect(DB); cur = conn.cursor()
        if pid:
            cur.execute("""
                SELECT appointment_id, date_time FROM appointments
                WHERE patient_id = ? ORDER BY date_time DESC
            """, (pid,))
        else:
            cur.execute("SELECT appointment_id, date_time FROM appointments ORDER BY date_time DESC")
        for aid, dt in cur.fetchall():
            self.appt_picker.addItem(f"{dt} (#{aid})", aid)
        conn.close()
        self.appt_picker.insertItem(0, "(None)", None)
        self.appt_picker.setCurrentIndex(0)

    def _filters(self):
        return (
            f"%{self.patient_filter.text().strip()}%",
            f"%{self.vet_filter.text().strip()}%",
            self.start_date.date().toString("yyyy-MM-dd"),
            self.end_date.date().toString("yyyy-MM-dd"),
        )

    def load_records(self):
        self.table.setRowCount(0)
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("""
            SELECT mr.record_id, mr.date_created, p.name,
                   COALESCE(mr.appointment_id, ''),
                   COALESCE(mr.vet_name,''),
                   COALESCE(mr.chief_complaint,''),
                   COALESCE(mr.diagnosis,''),
                   COALESCE(mr.follow_up_date,'')
              FROM medical_records mr
              JOIN patients p ON mr.patient_id = p.patient_id
             WHERE p.name LIKE ? AND COALESCE(mr.vet_name,'') LIKE ?
               AND DATE(mr.date_created) BETWEEN DATE(?) AND DATE(?)
             ORDER BY mr.date_created DESC
        """, self._filters())
        rows = cur.fetchall()
        conn.close()

        for r, row in enumerate(rows):
            self.table.insertRow(r)
            for c, val in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))

    # ---------- UI events ----------
    def on_new(self):
        self.selected_record_id = None
        if self.patient_picker.count() > 0:
            self.patient_picker.setCurrentIndex(0)
        self._reload_appt_list()
        self.vet_input.setCurrentIndex(0)
        for w in (self.chief_input, self.diag_input):
            w.clear()
        for w in (self.subj_input, self.obj_input, self.assess_input, self.plan_input):
            w.clear()
        self.follow_up.setDate(QDate.currentDate())

    def on_select_row(self):
        r = self.table.currentRow()
        if r < 0: return
        rec_id = int(self.table.item(r, 0).text())
        self.selected_record_id = rec_id

        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("""
            SELECT patient_id, appointment_id, vet_name, chief_complaint,
                   subjective, objective, assessment, plan, diagnosis, follow_up_date
              FROM medical_records WHERE record_id = ?
        """, (rec_id,))
        row = cur.fetchone()
        conn.close()
        if not row: return

        (pid, aid, vet, chief, subj, obj, assess, plan, diag, follow_up) = row
        idx = self.patient_picker.findData(pid)
        if idx >= 0: self.patient_picker.setCurrentIndex(idx)
        self._reload_appt_list()
        if aid:
            aidx = self.appt_picker.findData(aid)
            if aidx >= 0: self.appt_picker.setCurrentIndex(aidx)
        self.vet_input.setCurrentText(vet or "")
        self.chief_input.setText(chief or "")
        self.subj_input.setPlainText(subj or "")
        self.obj_input.setPlainText(obj or "")
        self.assess_input.setPlainText(assess or "")
        self.plan_input.setPlainText(plan or "")
        self.diag_input.setText(diag or "")
        if follow_up:
            try:
                self.follow_up.setDate(QDate.fromString(follow_up, "yyyy-MM-dd"))
            except:
                pass

    def on_save(self):
        pid = self.patient_picker.currentData()
        aid = self.appt_picker.currentData()  # can be None
        vet = self.vet_input.currentText().strip()
        chief = self.chief_input.text().strip()
        subj  = self.subj_input.toPlainText().strip()
        obj   = self.obj_input.toPlainText().strip()
        assess= self.assess_input.toPlainText().strip()
        plan  = self.plan_input.toPlainText().strip()
        diag  = self.diag_input.text().strip()
        fu    = self.follow_up.date().toString("yyyy-MM-dd")

        if not pid:
            QMessageBox.warning(self, "Input Error", "Select a patient.")
            return

        conn = sqlite3.connect(DB); cur = conn.cursor()
        if self.selected_record_id:
            cur.execute("""
                UPDATE medical_records
                   SET patient_id=?, appointment_id=?, vet_name=?, chief_complaint=?,
                       subjective=?, objective=?, assessment=?, plan=?, diagnosis=?, follow_up_date=?
                 WHERE record_id=?
            """, (pid, aid, vet, chief, subj, obj, assess, plan, diag, fu, self.selected_record_id))
        else:
            cur.execute("""
                INSERT INTO medical_records
                  (patient_id, appointment_id, vet_name, chief_complaint, subjective, objective, assessment, plan, diagnosis, follow_up_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (pid, aid, vet, chief, subj, obj, assess, plan, diag, fu))
            self.selected_record_id = cur.lastrowid
        conn.commit(); conn.close()

        QMessageBox.information(self, "Saved", "Medical record saved.")
        self.load_records()

    def on_delete(self):
        if not self.selected_record_id:
            return
        if QMessageBox.question(self, "Confirm", "Delete this record?") != QMessageBox.Yes:
            return
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("DELETE FROM medical_records WHERE record_id=?", (self.selected_record_id,))
        conn.commit(); conn.close()
        self.on_new()
        self.load_records()

    # ---------- Attachments ----------
    def on_add_attachment(self):
        if not self.selected_record_id:
            QMessageBox.warning(self, "No Record", "Save the record first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files to attach")
        if not paths: return

        conn = sqlite3.connect(DB); cur = conn.cursor()
        for src in paths:
            fname = os.path.basename(src)
            dst = os.path.join(ATTACH_DIR, f"{self.selected_record_id}_{int(datetime.now().timestamp())}_{fname}")
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                QMessageBox.critical(self, "Copy Failed", str(e)); continue
            mime = _guess_mime(fname)
            cur.execute("""
                INSERT INTO record_attachments (record_id, file_name, file_path, mime_type)
                VALUES (?,?,?,?)
            """, (self.selected_record_id, fname, dst, mime))
        conn.commit(); conn.close()
        QMessageBox.information(self, "Attached", "File(s) attached successfully.")

    def on_view_attachments(self):
        if not self.selected_record_id:
            return
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("""
            SELECT attachment_id, file_name, file_path, mime_type, uploaded_at
              FROM record_attachments WHERE record_id=?
              ORDER BY uploaded_at DESC
        """, (self.selected_record_id,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            QMessageBox.information(self, "Attachments", "No attachments for this record yet.")
            return
        # Simple listing dialog:
        txt = "\n".join([f"#{aid}  {fn}  [{mt}]  {when}\n{fp}" for aid, fn, fp, mt, when in rows])
        QMessageBox.information(self, "Attachments", txt)

    def focus_on_patient(self, patient_id: int, patient_name: str | None = None):
        """Jump to a new record with the given patient preselected."""
        # start a clean form
        self.on_new()
        # select the patient
        idx = self.patient_picker.findData(patient_id)
        if idx < 0:
            self._load_patient_list()
            idx = self.patient_picker.findData(patient_id)
        if idx >= 0:
            self.patient_picker.setCurrentIndex(idx)
            # refresh appointment choices for this patient
            self._reload_appt_list()
        # optional: bring window state up-to-date
        self.chief_input.setFocus()


def _guess_mime(fn: str) -> str:
    low = fn.lower()
    if low.endswith((".png",".jpg",".jpeg",".webp",".bmp")): return "image"
    if low.endswith((".pdf",)): return "application/pdf"
    if low.endswith((".mp4",".mov",".avi",".mkv")): return "video"
    return "file"
