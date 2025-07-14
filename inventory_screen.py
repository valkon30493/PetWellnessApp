# inventory_screen.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QLineEdit, QPlainTextEdit,
    QDoubleSpinBox, QSpinBox, QPushButton, QMessageBox, QFileDialog, QInputDialog
)
from PySide6.QtCore import Qt
import csv
import inventory

class InventoryScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventory Management")
        self.selected_item_id = None

        # Layouts
        main = QVBoxLayout(self)

        # Table
        self.table = QTableWidget(0,7)
        self.table.setHorizontalHeaderLabels([
            "ID","Name","Description","Cost","Price","On-Hand","Reorder Lvl"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.on_select)
        main.addWidget(self.table)

        # Form
        form = QFormLayout()
        self.name_in   = QLineEdit()
        self.desc_in   = QPlainTextEdit()
        self.cost_in   = QDoubleSpinBox(); self.cost_in.setMinimum(0)
        self.price_in  = QDoubleSpinBox(); self.price_in.setMinimum(0)
        self.thresh_in = QSpinBox(); self.thresh_in.setMinimum(0)
        form.addRow("Name:", self.name_in)
        form.addRow("Description:", self.desc_in)
        form.addRow("Unit Cost:", self.cost_in)
        form.addRow("Unit Price:", self.price_in)
        form.addRow("Reorder Threshold:", self.thresh_in)
        main.addLayout(form)

        # Buttons
        btns = QHBoxLayout()
        self.new_btn    = QPushButton("New")
        self.save_btn   = QPushButton("Save")
        self.delete_btn = QPushButton("Delete")
        self.adjust_btn = QPushButton("Adjust Stock")
        self.export_btn = QPushButton("Export Reorder Report")
        btns.addWidgets([self.new_btn, self.save_btn, self.delete_btn,
                         self.adjust_btn, self.export_btn])
        main.addLayout(btns)

        # Signals
        self.new_btn.clicked.connect(self.on_new)
        self.save_btn.clicked.connect(self.on_save)
        self.delete_btn.clicked.connect(self.on_delete)
        self.adjust_btn.clicked.connect(self.on_adjust)
        self.export_btn.clicked.connect(self.on_export)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for row in inventory.get_all_items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, v in enumerate(row):
                self.table.setItem(r,c, QTableWidgetItem(str(v)))

    def on_select(self):
        sel = self.table.currentRow()
        if sel<0: return
        self.selected_item_id = int(self.table.item(sel,0).text())
        self.name_in  .setText(self.table.item(sel,1).text())
        self.desc_in  .setPlainText(self.table.item(sel,2).text())
        self.cost_in  .setValue(float(self.table.item(sel,3).text()))
        self.price_in .setValue(float(self.table.item(sel,4).text()))
        self.thresh_in.setValue(int(self.table.item(sel,6).text()))

    def on_new(self):
        self.selected_item_id = None
        self.name_in.clear(); self.desc_in.clear()
        self.cost_in.setValue(0); self.price_in.setValue(0)
        self.thresh_in.setValue(0)

    def on_save(self):
        name = self.name_in.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error","Name is required.")
            return
        desc, cost, price, thr = (
            self.desc_in.toPlainText(), self.cost_in.value(),
            self.price_in.value(), self.thresh_in.value()
        )
        if self.selected_item_id:
            inventory.update_item(self.selected_item_id,
                                  name=name, description=desc,
                                  unit_cost=cost, unit_price=price,
                                  reorder_threshold=thr)
        else:
            inventory.create_item(name,desc,cost,price,thr)
        self.refresh()

    def on_delete(self):
        if not self.selected_item_id:
            return
        if QMessageBox.question(self,"Confirm","Delete this item?")!=QMessageBox.Yes:
            return
        inventory.delete_item(self.selected_item_id)
        self.on_new(); self.refresh()

    def on_adjust(self):
        if not self.selected_item_id:
            return
        qty, ok = QInputDialog.getInt(self,"Adjust Stock","Δ qty (+/-):",0)
        if not ok: return
        reason, ok = QInputDialog.getText(self,"Reason","Reason for adjustment:")
        if not ok: reason=None
        inventory.adjust_stock(self.selected_item_id,qty,reason)
        self.refresh()

    def on_export(self):
        path, _ = QFileDialog.getSaveFileName(self,"Save CSV","reorder_report.csv","*.csv")
        if not path: return
        rows = inventory.items_below_reorder()
        with open(path,"w",newline="") as f:
            w=csv.writer(f)
            w.writerow(["ID","Name","Desc","Cost","Price","Threshold","OnHand"])
            w.writerows(rows)
        QMessageBox.information(self,"Exported",f"Saved to {path}")
