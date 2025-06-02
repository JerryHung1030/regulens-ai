# ---------- Reference ProjectEditor (drop-in replacement) ----------
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFormLayout, QToolButton, QFileDialog, QInputDialog, QMessageBox,
    QStyle
)
from app.models.project import CompareProject


class ProjectEditor(QWidget):
    """Folder picker + compare launcher."""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent=None):
        super().__init__(parent)
        self.project = project
        self._base_css = "ProjectEditor { background-color: #ffffff; border-radius: 8px; }"
        self.setStyleSheet(self._base_css)
        self._build_ui()
        self.project.changed.connect(self._refresh)
        self._refresh()

    # ---------- UI ----------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)

        # Title row
        head = QHBoxLayout()
        self.lb_title = QLabel()
        self.lb_title.setStyleSheet("""
            QLabel {
                font-size: 16px; /* Adjusted from 22px */
                font-weight: 600; /* Bolder */
                color: #1A237E; /* Dark blue color for title */
                margin-bottom: 10px; /* Add some space below the title */
            }
        """)
        head.addWidget(self.lb_title)
        head.addWidget(self._tool_btn(QStyle.SP_FileDialogDetailedView, "Rename project", self._rename))
        head.addWidget(self._tool_btn(QStyle.SP_DialogDiscardButton, "Delete project", self._delete))
        head.addStretch()
        lay.addLayout(head)

        # Three folder pickers
        self._ctrl_edit, self._proc_edit, self._evid_edit = [QLineEdit(readOnly=True) for _ in range(3)]
        line_edit_style = """
            QLineEdit {
                background-color: #f8f9fa; /* Very light gray, almost white */
                border: 1px solid #ced4da; /* Standard input border color */
                padding: 8px 10px; /* Increased padding */
                border-radius: 4px;
                font-size: 14px; /* Slightly larger font */
                color: #495057; /* Text color */
            }
            QLineEdit:read-only { /* Ensure read-only also gets styled */
                background-color: #e9ecef; /* Slightly different bg for read-only if needed */
            }
        """
        self._ctrl_edit.setStyleSheet(line_edit_style)
        self._proc_edit.setStyleSheet(line_edit_style)
        self._evid_edit.setStyleSheet(line_edit_style)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow("Controls folder:", self._row(self._ctrl_edit, self._pick_ctrl))
        form.addRow("Procedures folder:", self._row(self._proc_edit, self._pick_proc))
        form.addRow("Evidences folder:", self._row(self._evid_edit, self._pick_evid))
        lay.addLayout(form)

        # Compare button
        self.btn_compare = QPushButton()
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        self.btn_compare.setStyleSheet("""
            QPushButton {
                padding: 12px 24px; /* More prominent padding */
                border-radius: 6px;
                background-color: #1a73e8; /* Google Blue */
                color: white;
                font-size: 16px; /* Larger font */
                font-weight: bold;
                border: none; /* Remove border for flat design */
            }
            QPushButton:hover {
                background-color: #1765cc; /* Darker blue for hover */
            }
            QPushButton:pressed {
                background-color: #1459b3; /* Even darker for pressed */
            }
            QPushButton:disabled {
                background-color: #e0e0e0; /* Lighter gray for disabled */
                color: #aaaaaa; /* Darker text for disabled */
            }
        """)
        lay.addWidget(self.btn_compare, alignment=Qt.AlignCenter)
        lay.addStretch()

    # ---------- Helpers ----------
    def _row(self, line, chooser):
        h = QHBoxLayout()
        h.addWidget(line)
        b = QPushButton("Browse…")
        b.setStyleSheet("""
            QPushButton {
                padding: 8px 12px; /* Match QLineEdit padding */
                background-color: #e9ecef; /* Light grayish blue */
                border: 1px solid #ced4da;
                border-radius: 4px;
                color: #495057;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #dee2e6;
            }
            QPushButton:pressed {
                background-color: #ced4da;
            }
        """)
        b.clicked.connect(chooser)
        h.addWidget(b)
        return h

    def _tool_btn(self, icon, tip, slot):
        btn = QToolButton()
        btn.setIcon(self.style().standardIcon(icon))
        btn.setToolTip(tip)
        btn.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 6px;
                border-radius: 4px;
                background-color: transparent;
                color: #555555; /* Icon color */
            }
            QToolButton:hover {
                background-color: #eeeeee; /* Lighter hover */
            }
            QToolButton:pressed {
                background-color: #dddddd;
            }
        """)
        btn.clicked.connect(slot)
        return btn

    # ---------- Folder pickers ----------
    def _pick_ctrl(self):
        self._pick("controls_dir", self._ctrl_edit)

    def _pick_proc(self): 
        self._pick("procedures_dir", self._proc_edit)

    def _pick_evid(self): 
        self._pick("evidences_dir", self._evid_edit)

    def _pick(self, attr, edit):
        start = str(getattr(self.project, attr) or Path.home())
        path = QFileDialog.getExistingDirectory(self, "Select folder", start)
        if path:
            setattr(self.project, attr, Path(path))
            self.project.changed.emit()

    # ---------- Project operations ----------
    def _rename(self):
        new, ok = QInputDialog.getText(self, "Rename project", "New name:", text=self.project.name)
        if ok and new: 
            self.project.rename(new)
            
    def _delete(self):
        if QMessageBox.question(self, "Delete", f'Delete "{self.project.name}"?') == QMessageBox.Yes:
            self.project.deleted.emit()

    # ---------- Refresh ----------
    def _refresh(self):
        self.lb_title.setText(f"<h2>{self.project.name}</h2>")
        self._ctrl_edit.setText(str(self.project.controls_dir or ""))
        self._proc_edit.setText(str(self.project.procedures_dir or ""))
        self._evid_edit.setText(str(self.project.evidences_dir or ""))

        if self.project.is_sample:
            self.btn_compare.setText("Re-run sample")
            bg_color_sample = "#e3f2fd" if self.project.name == "強密碼合規範例" else "#f1f8e9"
            self.setStyleSheet(f"ProjectEditor {{ background-color: {bg_color_sample}; border-radius: 8px; border: 2px dashed #757575; }}")
        else:
            self.btn_compare.setText("Start compare")
            self.setStyleSheet(self._base_css)  # Apply the base style for non-sample projects

        self.btn_compare.setEnabled(self.project.ready)
# --------------------------------------------------------------------
