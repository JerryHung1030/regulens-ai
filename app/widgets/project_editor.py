from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QPushButton,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QStyle,
    QLineEdit, # Added
    QFormLayout, # Added for better layout
)

from app.models.project import CompareProject


class ProjectEditor(QWidget):
    """用於選擇檔案與啟動比較的介面"""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        # Initialize to an empty string or a default style
        self._base_stylesheet = "ProjectEditor { padding: 1px; }" # Ensure padding for border visibility
        self.setStyleSheet(self._base_stylesheet)


        self._build_ui()
        self.project.changed.connect(self._refresh)
        self._refresh() # Load project data into UI

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setSpacing(15) # Adjusted spacing
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Project Title and Action Buttons (Rename, Delete)
        title_row_layout = QHBoxLayout()
        self.title_label = QLabel(f"<h2>{self.project.name}</h2>") # Made it a member for easier update
        self.title_label.setStyleSheet("margin: 0;")
        title_row_layout.addWidget(self.title_label)

        btn_rename = QToolButton()
        btn_rename.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        btn_rename.setToolTip("重命名專案")
        btn_rename.setStyleSheet("QToolButton { border: none; padding: 4px; border-radius: 4px; } QToolButton:hover { background-color: #e0e0e0; }")
        btn_rename.clicked.connect(self._rename_project)
        title_row_layout.addWidget(btn_rename)

        btn_delete = QToolButton()
        btn_delete.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        btn_delete.setToolTip("刪除專案")
        btn_delete.setStyleSheet("QToolButton { border: none; padding: 4px; border-radius: 4px; } QToolButton:hover { background-color: #ffebee; }")
        btn_delete.clicked.connect(self._delete_project)
        title_row_layout.addWidget(btn_delete)
        title_row_layout.addStretch()
        main_layout.addLayout(title_row_layout)

        # Form layout for directory selection
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight) # Align labels to the right

        # Controls Directory
        self.controls_dir_edit = QLineEdit()
        self.controls_dir_edit.setReadOnly(True)
        btn_choose_controls = QPushButton("選擇資料夾...")
        btn_choose_controls.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        btn_choose_controls.clicked.connect(self._choose_controls_dir)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.controls_dir_edit)
        controls_layout.addWidget(btn_choose_controls)
        form_layout.addRow("控制措施 (Controls):", controls_layout)

        # Procedures Directory
        self.procedures_dir_edit = QLineEdit()
        self.procedures_dir_edit.setReadOnly(True)
        btn_choose_procedures = QPushButton("選擇資料夾...")
        btn_choose_procedures.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        btn_choose_procedures.clicked.connect(self._choose_procedures_dir)
        procedures_layout = QHBoxLayout()
        procedures_layout.addWidget(self.procedures_dir_edit)
        procedures_layout.addWidget(btn_choose_procedures)
        form_layout.addRow("實施程序 (Procedures):", procedures_layout)

        # Evidences Directory
        self.evidences_dir_edit = QLineEdit()
        self.evidences_dir_edit.setReadOnly(True)
        btn_choose_evidences = QPushButton("選擇資料夾...")
        btn_choose_evidences.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        btn_choose_evidences.clicked.connect(self._choose_evidences_dir)
        evidences_layout = QHBoxLayout()
        evidences_layout.addWidget(self.evidences_dir_edit)
        evidences_layout.addWidget(btn_choose_evidences)
        form_layout.addRow("佐證資料 (Evidences):", evidences_layout)
        
        main_layout.addLayout(form_layout)
        main_layout.addSpacing(10) # Add some space before the compare button

        # Comparison Button
        self.btn_compare = QPushButton("開始比較") # Text will be updated in _refresh
        self.btn_compare.setStyleSheet("""
            QPushButton {
                padding: 10px 20px; /* Adjusted padding */
                border-radius: 6px;
                background-color: #2196f3;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
                color: #757575; /* Darker text for disabled state */
            }
        """)
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        main_layout.addWidget(self.btn_compare, alignment=Qt.AlignCenter)
        main_layout.addStretch() # Push button and form upwards

    def _choose_directory(self, target_attribute: str, line_edit_widget: QLineEdit):
        current_path_str = getattr(self.project, target_attribute)
        start_dir = str(current_path_str) if current_path_str else str(Path.home())

        dir_path = QFileDialog.getExistingDirectory(
            self,
            "選擇資料夾",
            start_dir
        )

        if dir_path:
            selected_path = Path(dir_path)

            if self.project.is_sample:
                has_non_txt = any(f.is_file() and f.suffix.lower() != ".txt" for f in selected_path.iterdir())
                if has_non_txt:
                    QMessageBox.warning(self, "檔案類型限制", "Demo版目前僅支援純文字 (.txt) 檔案。")
                    # Optionally, prevent setting the path or clear it if non-txt are found and it's critical
                    # For now, we warn but still set the path. The `ready` property will ultimately decide.

            setattr(self.project, target_attribute, selected_path)
            line_edit_widget.setText(str(selected_path))
            self.project.changed.emit() # This will trigger _refresh, which calls _update_compare_button_state

    def _choose_controls_dir(self):
        self._choose_directory("controls_dir", self.controls_dir_edit)

    def _choose_procedures_dir(self):
        self._choose_directory("procedures_dir", self.procedures_dir_edit)

    def _choose_evidences_dir(self):
        self._choose_directory("evidences_dir", self.evidences_dir_edit)

    def _update_compare_button_state(self):
        is_ready = self.project.ready
        self.btn_compare.setEnabled(is_ready)

        # Update button text and style based on sample status
        current_stylesheet = self.styleSheet() # Get current combined stylesheet
        border_style = ""

        if self.project.is_sample:
            self.btn_compare.setText("重新執行範例")
            border_style = "ProjectEditor { border: 2px dashed gray; padding: 1px; }" # Ensure padding for border
            if self.project.name == "強密碼合規範例":
                bg_color = "#e3f2fd"
            elif self.project.name == "風險清冊範例":
                bg_color = "#f1f8e9"
            else:
                bg_color = "transparent" # Or a default sample bg
            # Combine border with existing background
            self.setStyleSheet(f"{border_style} ProjectEditor {{ background-color: {bg_color}; }}")

        else:
            self.btn_compare.setText("開始比較")
            # Reset to base stylesheet (removes border and specific sample background)
            # This assumes _base_stylesheet only contains ProjectEditor padding or similar non-dynamic styles.
            self.setStyleSheet(self._base_stylesheet)


    def _rename_project(self):
        name, ok = QInputDialog.getText(
            self,
            "重命名專案",
            "請輸入新的專案名稱：",
            text=self.project.name
        )
        if ok and name:
            self.project.rename(name)  # Emits project.updated

    def _delete_project(self):
        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除專案「{self.project.name}」嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.project.deleted.emit()

    # ------------------------------------------------------------------
    def _refresh(self):
        """更新 UI 顯示"""
        # 更新標題
        title = self.findChild(QLabel)
        if title:
            title.setText(f"<h2>{self.project.name}</h2>")
        
        # Update title
        self.title_label.setText(f"<h2>{self.project.name}</h2>")

        # Update QLineEdit fields
        self.controls_dir_edit.setText(str(self.project.controls_dir) if self.project.controls_dir else "")
        self.procedures_dir_edit.setText(str(self.project.procedures_dir) if self.project.procedures_dir else "")
        self.evidences_dir_edit.setText(str(self.project.evidences_dir) if self.project.evidences_dir else "")

        # Update button state and visual styling for sample projects
        self._update_compare_button_state()
