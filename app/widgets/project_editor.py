# ---------- Reference ProjectEditor (drop-in replacement) ----------
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import *
from app.models.project import CompareProject

class ProjectEditor(QWidget):
    """Folder picker + compare launcher."""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent=None):
        super().__init__(parent)
        self.project = project
        self._base_css = "ProjectEditor{padding:1px;}"
        self.setStyleSheet(self._base_css)
        self._build_ui()
        self.project.changed.connect(self._refresh)
        self._refresh()

    # ---------- UI ----------
    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)

        # Title row
        head = QHBoxLayout()
        self.lb_title = QLabel(); head.addWidget(self.lb_title)
        head.addWidget(self._tool_btn(QStyle.SP_FileDialogDetailedView, "Rename project", self._rename))
        head.addWidget(self._tool_btn(QStyle.SP_DialogDiscardButton,    "Delete project", self._delete))
        head.addStretch(); lay.addLayout(head)

        # Three folder pickers
        self._ctrl_edit, self._proc_edit, self._evid_edit = [QLineEdit(readOnly=True) for _ in range(3)]
        form = QFormLayout(); form.setSpacing(10); form.setLabelAlignment(Qt.AlignRight)
        form.addRow("Controls folder:",   self._row(self._ctrl_edit, self._pick_ctrl))
        form.addRow("Procedures folder:", self._row(self._proc_edit, self._pick_proc))
        form.addRow("Evidences folder:",  self._row(self._evid_edit, self._pick_evid))
        lay.addLayout(form)

        # Compare button
        self.btn_compare = QPushButton()
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        self.btn_compare.setStyleSheet("""
            QPushButton{padding:10px 20px;border-radius:6px;background:#2196f3;color:#fff;font-weight:bold;}
            QPushButton:hover{background:#1976d2;}
            QPushButton:disabled{background:#bdbdbd;color:#757575;}
        """)
        lay.addWidget(self.btn_compare, alignment=Qt.AlignCenter); lay.addStretch()

    # ---------- Helpers ----------
    def _row(self, line, chooser):
        h = QHBoxLayout(); h.addWidget(line); b = QPushButton("Browse…"); b.clicked.connect(chooser); h.addWidget(b); return h
    def _tool_btn(self, icon, tip, slot):
        btn = QToolButton(); btn.setIcon(self.style().standardIcon(icon)); btn.setToolTip(tip)
        btn.setStyleSheet("QToolButton{border:none;padding:4px;border-radius:4px;}QToolButton:hover{background:#e0e0e0;}")
        btn.clicked.connect(slot); return btn

    # ---------- Folder pickers ----------
    def _pick_ctrl(self): self._pick("controls_dir",   self._ctrl_edit)
    def _pick_proc(self): self._pick("procedures_dir", self._proc_edit)
    def _pick_evid(self): self._pick("evidences_dir",  self._evid_edit)
    def _pick(self, attr, edit):
        start = str(getattr(self.project, attr) or Path.home())
        path = QFileDialog.getExistingDirectory(self, "Select folder", start)
        if path: setattr(self.project, attr, Path(path)); self.project.changed.emit()

    # ---------- Project operations ----------
    def _rename(self):
        new, ok = QInputDialog.getText(self, "Rename project", "New name:", text=self.project.name)
        if ok and new: self.project.rename(new)
    def _delete(self):
        if QMessageBox.question(self, "Delete", f"Delete “{self.project.name}”?") == QMessageBox.Yes:
            self.project.deleted.emit()

    # ---------- Refresh ----------
    def _refresh(self):
        self.lb_title.setText(f"<h2>{self.project.name}</h2>")
        self._ctrl_edit.setText(str(self.project.controls_dir or ""))
        self._proc_edit.setText(str(self.project.procedures_dir or ""))
        self._evid_edit.setText(str(self.project.evidences_dir or ""))

        if self.project.is_sample:
            self.btn_compare.setText("Re-run sample")
            bg = "#e3f2fd" if self.project.name == "強密碼合規範例" else "#f1f8e9"
            self.setStyleSheet(f"{self._base_css}ProjectEditor{{border:2px dashed gray;background:{bg};}}")
        else:
            self.btn_compare.setText("Start compare")
            self.setStyleSheet(self._base_css)

        self.btn_compare.setEnabled(self.project.ready)
# --------------------------------------------------------------------
