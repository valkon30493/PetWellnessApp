# consent_forms.py
import os, sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QLabel, QFileDialog, QMessageBox, QFormLayout,
    QDateEdit, QHeaderView, QCheckBox
)
from PySide6.QtCore import QDate, Signal
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas

DB = "vet_management.db"

class ConsentFormsScreen(QWidget):
    # Allows Patient screen to preselect a patient & open "new consent" quickly
    create_for_patient = Signal(int, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Consent Forms")
        self.selected_consent_id = None
        self.selected_patient_id = None

        # flags for template <-> field syncing
        self._populating = False
        self._dirty_type = False
        self._dirty_body = False

        main = QVBoxLayout(self)

        # Top row: search/filter
        filters = QHBoxLayout()
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Search by patient or form type…")
        self.search_input.textChanged.connect(self.load_forms)
        self.status_filter = QComboBox(); self.status_filter.addItems(["All","Draft","Signed","Voided"])
        self.status_filter.currentIndexChanged.connect(self.load_forms)
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1)); self.date_from.setCalendarPopup(True)
        self.date_to   = QDateEdit(QDate.currentDate()); self.date_to.setCalendarPopup(True)
        filters.addWidget(QLabel("From:")); filters.addWidget(self.date_from)
        filters.addWidget(QLabel("To:"));   filters.addWidget(self.date_to)
        self.date_from.dateChanged.connect(self.load_forms)
        self.date_to.dateChanged.connect(self.load_forms)
        filters.addWidget(self.search_input)
        filters.addWidget(QLabel("Status:")); filters.addWidget(self.status_filter)
        main.addLayout(filters)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID","Patient","Type","Status","Follow‑up","Signed By","Relation","Created"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_select)
        main.addWidget(self.table)

        # Form
        form = QFormLayout()
        self.patient_display = QLineEdit(); self.patient_display.setReadOnly(True)
        self.template_combo  = QComboBox()
        self.keep_sync_cb    = QCheckBox("Keep fields synced to template")
        self.keep_sync_cb.setChecked(True)

        self.form_type_in    = QLineEdit()
        self.body_text       = QTextEdit()
        self.signed_by_in    = QLineEdit()
        self.relation_in     = QComboBox(); self.relation_in.addItems(["","Owner","Guardian","Other"])
        self.follow_up_in    = QDateEdit(); self.follow_up_in.setCalendarPopup(True)
        self.follow_up_in.setDate(QDate.currentDate().addDays(7))

        form.addRow("Patient:", self.patient_display)
        form.addRow("Template:", self.template_combo)
        form.addRow("", self.keep_sync_cb)
        form.addRow("Form Type:", self.form_type_in)
        form.addRow("Body:", self.body_text)
        form.addRow("Signed By:", self.signed_by_in)
        form.addRow("Relation:", self.relation_in)
        form.addRow("Follow‑up Date:", self.follow_up_in)
        main.addLayout(form)

        # Buttons
        btns = QHBoxLayout()
        self.new_btn     = QPushButton("New")
        self.save_btn    = QPushButton("Save")
        self.sign_btn    = QPushButton("Mark as Signed…")
        self.void_btn    = QPushButton("Void")
        self.export_btn  = QPushButton("Export PDF")
        self.attach_sig  = QPushButton("Attach Signature Image")
        for b in (self.new_btn,self.save_btn,self.sign_btn,self.void_btn,self.attach_sig,self.export_btn):
            btns.addWidget(b)
        main.addLayout(btns)

        # Wire up
        self.new_btn.clicked.connect(self.on_new)
        self.save_btn.clicked.connect(self.on_save)
        self.sign_btn.clicked.connect(self.on_mark_signed)
        self.void_btn.clicked.connect(self.on_void)
        self.export_btn.clicked.connect(self.on_export_pdf)
        self.attach_sig.clicked.connect(self.on_attach_signature)
        self.create_for_patient.connect(self._prefill_for_patient)

        # Field-dirty tracking for sync logic
        self.form_type_in.textChanged.connect(self._on_type_changed_by_user)
        self.body_text.textChanged.connect(self._on_body_changed_by_user)

        # Seed templates & load
        self._load_templates()
        self.load_forms()
        self.on_new()

    # Public API from Patient screen:
    def quick_create_for(self, patient_id: int, patient_name: str):
        self.create_for_patient.emit(patient_id, patient_name)

    # Internal: called by signal
    def _prefill_for_patient(self, pid: int, pname: str):
        self.selected_patient_id = pid
        self.patient_display.setText(f"{pname} (ID:{pid})")
        # If template selected, auto-merge basic tokens:
        self._apply_template_to_fields(force=True)

    # ---------- Templates ----------
    def _load_templates(self):
        self.template_combo.clear()
        self.template_combo.addItem("— None —", None)
        conn = sqlite3.connect(DB); cur = conn.cursor()
        # optional table consent_templates(name, body_text) expected
        try:
            cur.execute("SELECT template_id, name FROM consent_templates ORDER BY name")
            for tid, name in cur.fetchall():
                self.template_combo.addItem(name, tid)
        except Exception:
            # If templates table doesn't exist, we still allow free typing
            pass
        conn.close()
        self.template_combo.currentIndexChanged.connect(lambda _=None: self._apply_template_to_fields())

    def _fetch_template_body(self, tid):
        if not tid:
            return ""
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("SELECT body_text FROM consent_templates WHERE template_id=?", (tid,))
        row = cur.fetchone()
        conn.close()
        return (row[0] if row else "") or ""

    def _merge_tokens(self, text: str) -> str:
        owner_name, patient_name, today = "", "", datetime.now().strftime("%Y-%m-%d")
        if self.selected_patient_id:
            conn = sqlite3.connect(DB); cur = conn.cursor()
            try:
                cur.execute("SELECT owner_name, name FROM patients WHERE patient_id=?", (self.selected_patient_id,))
                r = cur.fetchone()
                if r:
                    owner_name, patient_name = r
            finally:
                conn.close()
        return (text or "").replace("{owner_name}", owner_name or "")\
                           .replace("{patient_name}", patient_name or "")\
                           .replace("{date}", today)

    def _apply_template_to_fields(self, force: bool = False):
        if not self.keep_sync_cb.isChecked() and not force:
            return
        tid = self.template_combo.currentData()
        if tid is None:
            return
        body = self._merge_tokens(self._fetch_template_body(tid))
        form_type_name = self.template_combo.currentText()

        self._populating = True
        try:
            # only overwrite if forcing, or fields not dirty, or sync is on
            if force or not self._dirty_type or self.keep_sync_cb.isChecked():
                self.form_type_in.setText(form_type_name or "Consent")
                self._dirty_type = False
            if force or not self._dirty_body or self.keep_sync_cb.isChecked():
                self.body_text.setPlainText(body)
                self._dirty_body = False
        finally:
            self._populating = False

    def _on_type_changed_by_user(self, _):
        if self._populating: return
        self._dirty_type = True
        # optional: stop syncing automatically after manual edit
        self.keep_sync_cb.setChecked(False)

    def _on_body_changed_by_user(self):
        if self._populating: return
        self._dirty_body = True
        self.keep_sync_cb.setChecked(False)

    # ---------- Table load ----------
    def load_forms(self):
        term = (self.search_input.text() or "").lower()
        status = self.status_filter.currentText()
        d1 = self.date_from.date().toString("yyyy-MM-dd")
        d2 = self.date_to.date().toString("yyyy-MM-dd")
        conn = sqlite3.connect(DB); cur = conn.cursor()
        q = """
            SELECT c.consent_id, p.name, c.form_type, c.status, c.follow_up_date,
                   c.signed_by, c.relation, c.created_at, p.patient_id
            FROM consent_forms c
            JOIN patients p ON p.patient_id = c.patient_id
            WHERE DATE(c.created_at) BETWEEN DATE(?) AND DATE(?)
        """
        params = [d1, d2]
        if status != "All":
            q += " AND c.status = ?"; params.append(status)
        if term:
            q += " AND (LOWER(p.name) LIKE ? OR LOWER(c.form_type) LIKE ?)"
            params.extend([f"%{term}%", f"%{term}%"])
        cur.execute(q, params)
        rows = cur.fetchall(); conn.close()

        self.table.setRowCount(0)
        for r, row in enumerate(rows):
            self.table.insertRow(r)
            for c, v in enumerate(row[:8]):  # hide patient_id in table
                self.table.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))

    def _on_select(self):
        r = self.table.currentRow()
        if r < 0: return
        cid = int(self.table.item(r, 0).text())
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("""
            SELECT c.patient_id, p.name, c.form_type, c.body_text, c.signed_by, c.relation,
                   c.status, c.follow_up_date, c.signature_path
            FROM consent_forms c
            JOIN patients p ON p.patient_id=c.patient_id
            WHERE c.consent_id=?
        """,(cid,))
        row = cur.fetchone(); conn.close()
        if not row: return
        (pid, pname, ftype, body, signed_by, relation, status, fup, sigpath) = row

        self._populating = True
        try:
            self.selected_consent_id = cid
            self.selected_patient_id = pid
            self.patient_display.setText(f"{pname} (ID:{pid})")
            self.form_type_in.setText(ftype or "")
            self.body_text.setPlainText(body or "")
            self.signed_by_in.setText(signed_by or "")
            self.relation_in.setCurrentText(relation or "")
            if fup:
                self.follow_up_in.setDate(QDate.fromString(fup, "yyyy-MM-dd"))
            self.sign_btn.setEnabled(status != "Signed")
            self.void_btn.setEnabled(status != "Voided")
            # for existing records, disable auto-sync by default to avoid stomping content
            self.keep_sync_cb.setChecked(False)
            self._dirty_type = False
            self._dirty_body = False
        finally:
            self._populating = False

    # ---------- CRUD ----------
    def on_new(self):
        self._populating = True
        try:
            self.selected_consent_id = None
            # keep selected_patient_id if user came from Patient screen
            self.form_type_in.clear()
            self.body_text.clear()
            self.signed_by_in.clear()
            self.relation_in.setCurrentIndex(0)
            self.follow_up_in.setDate(QDate.currentDate().addDays(7))
            self.sign_btn.setEnabled(False)
            self.void_btn.setEnabled(False)
            # reset sync flags
            self.keep_sync_cb.setChecked(True)
            self._dirty_type = False
            self._dirty_body = False
        finally:
            self._populating = False

    def on_save(self):
        if not self.selected_patient_id:
            QMessageBox.warning(self, "Missing", "Select a patient first.")
            return
        form_type = self.form_type_in.text().strip() or "Consent"
        body = self.body_text.toPlainText().strip()
        if not body:
            QMessageBox.warning(self, "Missing", "Body text is required.")
            return
        fup       = self.follow_up_in.date().toString("yyyy-MM-dd")
        signed_by = (self.signed_by_in.text().strip() or None)
        relation  = (self.relation_in.currentText().strip() or None)
        tid       = self.template_combo.currentData()

        conn = sqlite3.connect(DB); cur = conn.cursor()
        if self.selected_consent_id:
            cur.execute("""
                UPDATE consent_forms
                   SET template_id=?, form_type=?, body_text=?, follow_up_date=?, signed_by=?, relation=?
                 WHERE consent_id=?
            """, (tid, form_type, body, fup, signed_by, relation, self.selected_consent_id))
        else:
            cur.execute("""
                INSERT INTO consent_forms (patient_id, template_id, form_type, body_text, follow_up_date, status, signed_by, relation)
                VALUES (?,?,?,?,?, 'Draft', ?, ?)
            """, (self.selected_patient_id, tid, form_type, body, fup, signed_by, relation))
            self.selected_consent_id = cur.lastrowid
        conn.commit(); conn.close()
        self.load_forms()
        QMessageBox.information(self, "Saved", "Consent saved.")

    def on_mark_signed(self):
        if not self.selected_consent_id:
            return
        signer = self.signed_by_in.text().strip()
        if not signer:
            QMessageBox.warning(self, "Missing", "Enter 'Signed By' before marking as Signed.")
            return
        relation = self.relation_in.currentText()
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("""
            UPDATE consent_forms
               SET signed_by=?, relation=?, status='Signed'
             WHERE consent_id=?
        """, (signer, relation, self.selected_consent_id))
        conn.commit(); conn.close()
        self.load_forms()
        QMessageBox.information(self, "Marked", "Consent marked as Signed.")

    def on_void(self):
        if not self.selected_consent_id:
            return
        if QMessageBox.question(self, "Void", "Void this consent?") != QMessageBox.Yes:
            return
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("UPDATE consent_forms SET status='Voided' WHERE consent_id=?",(self.selected_consent_id,))
        conn.commit(); conn.close()
        self.load_forms()

    def on_attach_signature(self):
        """Store a path to a scanned signature image (PNG/JPG)."""
        if not self.selected_consent_id:
            QMessageBox.warning(self, "No Consent", "Save the consent first.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Attach Signature Image", "", "Images (*.png *.jpg *.jpeg)")
        if not path: return
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("UPDATE consent_forms SET signature_path=? WHERE consent_id=?",(path,self.selected_consent_id))
        conn.commit(); conn.close()
        QMessageBox.information(self, "Attached", "Signature image attached.")

    # ---------- PDF ----------
    def on_export_pdf(self):
        if not self.selected_consent_id:
            QMessageBox.warning(self, "No Consent", "Select a consent first.")
            return
        # fetch data
        conn = sqlite3.connect(DB); cur = conn.cursor()
        cur.execute("""
            SELECT c.consent_id, p.name, p.owner_name, c.form_type, c.body_text,
                   c.signed_by, c.relation, c.signature_path, c.created_at
            FROM consent_forms c
            JOIN patients p ON p.patient_id=c.patient_id
            WHERE c.consent_id=?
        """,(self.selected_consent_id,))
        row = cur.fetchone(); conn.close()
        if not row: return
        (cid, pet, owner, ftype, body, signed_by, relation, sig_path, created) = row
        default_fn = f"Consent_{cid}_{pet.replace(' ','')}.pdf"
        out, _ = QFileDialog.getSaveFileName(self, "Save PDF", default_fn, "PDF Files (*.pdf)")
        if not out: return
        try:
            pdf = pdf_canvas.Canvas(out, pagesize=A4)
            W, H = A4
            y = H - 50
            pdf.setFont("Helvetica-Bold", 14); pdf.drawString(50,y, f"{ftype}"); y -= 20
            pdf.setFont("Helvetica", 10)
            pdf.drawString(50,y, f"Patient: {pet}"); y -= 14
            pdf.drawString(50,y, f"Owner: {owner}"); y -= 14
            pdf.drawString(50,y, f"Created: {created}"); y -= 20
            # body (simple wrap)
            pdf.setFont("Helvetica", 10)
            for line in (body or "").splitlines():
                for chunk in [line[i:i+95] for i in range(0,len(line),95)]:
                    pdf.drawString(50,y, chunk); y -= 12
                    if y < 80: pdf.showPage(); y = H-50; pdf.setFont("Helvetica",10)
            y -= 20
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50,y, f"Signed By: {signed_by or ''}    Relation: {relation or ''}"); y -= 40
            # signature image if any
            if sig_path and os.path.exists(sig_path):
                try:
                    pdf.drawImage(sig_path, 50, y-60, width=200, height=60, preserveAspectRatio=True, mask='auto')
                    y -= 70
                except Exception:
                    pass
            pdf.line(50, y, 250, y); y -= 12
            pdf.drawString(50, y, "Signature")
            pdf.save()
            QMessageBox.information(self, "Exported", f"Saved to {out}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create PDF:\n{e}")
