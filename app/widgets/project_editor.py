# ---------- Reference ProjectEditor (drop-in replacement) ----------
from __future__ import annotations
from pathlib import Path
import json
from PySide6.QtCore import Qt, Signal # QDir removed, QFileSystemModel removed from imports
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QToolButton, QFileDialog, QInputDialog, QMessageBox,
    QStyle, QTextEdit, QTabWidget, QSplitter, QSizePolicy, # QTreeView removed (or only used if needed for specific previews)
    QListView # QListView is used for procedures
)
from PySide6.QtCore import QStringListModel
from app.models.project import CompareProject
from app.logger import logger


class ProjectEditor(QWidget):
    """Folder picker + compare launcher."""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent=None):
        super().__init__(parent)
        self.project = project
        # Updated base CSS for the card look
        # self._base_css = """
        #     ProjectEditor {
        #         background-color: #ffffff;
        #         border-radius: 8px;
        #         border: 1px solid #dadce0;
        #     }
        # """
        # self.setStyleSheet(self._base_css) # Remove this line

        # QFileSystemModels are no longer used for controls/procedures previews directly
        # self.controls_fs_model = QFileSystemModel() ... removed
        # self.procedures_fs_model = QFileSystemModel() ... removed
        # self.evidences_fs_model = QFileSystemModel() ... removed

        self._preview_is_visible = False  # For in-session state

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
        # Remove the setStyleSheet call below this line
        # self.lb_title.setStyleSheet("""
        #     QLabel {
        #         font-size: 20px;
        #         font-weight: 600;
        #         color: #202124; /* Google's primary text color */
        #         margin-bottom: 15px; 
        #     }
        # """)
        head.addWidget(self.lb_title)
        # Tool buttons are styled in _tool_btn method
        head.addWidget(self._tool_btn(QStyle.SP_FileDialogDetailedView, "Rename project", self._rename))
        head.addWidget(self._tool_btn(QStyle.SP_DialogDiscardButton, "Delete project", self._delete))
        head.addStretch()
        lay.addLayout(head)

        # Folder Selection Area
        self.folder_selection_container = QWidget()
        # Remove the setStyleSheet call below this line
        # self.folder_selection_container.setStyleSheet("margin-bottom: 20px;")  # Space before compare button
        folder_selection_layout = QVBoxLayout(self.folder_selection_container)
        folder_selection_layout.setContentsMargins(0, 0, 0, 0)
        folder_selection_layout.setSpacing(10)

        self._ctrl_edit, self._proc_edit = [QLineEdit(readOnly=True) for _ in range(2)] # _evid_edit removed
        
        # Remove the setStyleSheet call below this line
        # line_edit_stylesheet = """
        #     QLineEdit {
        #         font-size: 14px;
        #         padding: 8px 10px;
        #         border-radius: 4px;
        #         border: 1px solid #dadce0;
        #         background-color: #f8f9fa;
        #         color: #202124;
        #     }
        #     QLineEdit:read-only {
        #         background-color: #f1f3f4;
        #     }
        #     QLineEdit:focus {
        #         border-color: #1a73e8; /* Google Blue focus */
        #     }
        # """
        for edit_widget in [self._ctrl_edit, self._proc_edit]: # _evid_edit removed
            # Remove the setStyleSheet call below this line
            pass # Keep pass or other logic if needed after removing setStyleSheet

        # Controls Row
        controls_row_layout = QHBoxLayout()
        controls_row_layout.setAlignment(Qt.AlignVCenter)
        controls_label = QLabel("Controls JSON File:")
        controls_label.setObjectName("controls_json_file_label")
        controls_label.setFixedWidth(180)
        controls_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_row_layout.addWidget(controls_label)

        browse_ctrl_button = QPushButton("Browse…")
        browse_ctrl_button.setObjectName("controls_json_file_browse_button")
        browse_ctrl_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        browse_ctrl_button.clicked.connect(self._pick_ctrl)
        controls_row_layout.addWidget(browse_ctrl_button)
        controls_row_layout.addWidget(self._ctrl_edit)
        
        self.validate_json_button = QPushButton("Validate JSON")
        self.validate_json_button.setObjectName("validate_json_button")
        self.validate_json_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.validate_json_button.clicked.connect(self._validate_controls_json)
        # Initially disable validate button until a file is chosen
        self.validate_json_button.setEnabled(False)
        controls_row_layout.addWidget(self.validate_json_button)
        folder_selection_layout.addLayout(controls_row_layout)

        # Procedures Row
        procedures_row_layout = QHBoxLayout()
        procedures_row_layout.setAlignment(Qt.AlignVCenter)
        procedures_label = QLabel("Procedure Documents:")
        procedures_label.setObjectName("procedure_doc_files_label")
        procedures_label.setFixedWidth(180)
        procedures_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        procedures_row_layout.addWidget(procedures_label)

        browse_proc_button = QPushButton("Browse…")
        browse_proc_button.setObjectName("procedure_doc_files_browse_button")
        browse_proc_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        browse_proc_button.clicked.connect(self._pick_proc)
        procedures_row_layout.addWidget(browse_proc_button)
        procedures_row_layout.addWidget(self._proc_edit)
        folder_selection_layout.addLayout(procedures_row_layout)

        # Evidences row is removed.

        lay.addWidget(self.folder_selection_container)

        # File Preview Section - Before Compare button
        self.preview_container = QWidget()
        self.preview_container.setObjectName("previewContainer")
        preview_container_layout = QVBoxLayout(self.preview_container)
        preview_container_layout.setContentsMargins(0, 10, 0, 0)  # Add some top margin

        self.toggle_preview_button = QPushButton()  # Text set based on _preview_is_visible
        self.toggle_preview_button.setObjectName("togglePreviewButton")
        preview_container_layout.addWidget(self.toggle_preview_button)

        self.preview_content_area = QWidget()
        preview_content_layout = QVBoxLayout(self.preview_content_area)
        preview_content_layout.setContentsMargins(0, 5, 0, 0)  # Small margin
        preview_container_layout.addWidget(self.preview_content_area)

        self.preview_tab_widget = QTabWidget()
        self.preview_tab_widget.setObjectName("previewTabWidget")
        preview_content_layout.addWidget(self.preview_tab_widget)

        # Create tabs: Controls (JSON), Procedures (PDF List)
        # Evidences tab is removed.
        self.preview_tab_widget.clear() # Clear existing tabs if any during a refresh scenario (though _build_ui is usually once)

        # Controls Tab
        controls_tab_content_widget = QWidget()
        controls_tab_layout = QVBoxLayout(controls_tab_content_widget)
        controls_tab_layout.setContentsMargins(0,0,0,0)
        controls_splitter = QSplitter(Qt.Horizontal)
        
        # 左側：檔案名稱列表
        self.controls_list_view = QListView()
        self.controls_list_view.setObjectName("controlsListView")
        self.controls_list_view.clicked.connect(self._on_control_file_selected)
        controls_splitter.addWidget(self.controls_list_view)
        
        # 右側：檔案內容預覽
        self.controls_json_preview = QTextEdit()
        self.controls_json_preview.setReadOnly(True)
        self.controls_json_preview.setObjectName("controlsJsonPreview")
        controls_splitter.addWidget(self.controls_json_preview)
        
        controls_splitter.setSizes([200, 300])  # 設定左右兩側的預設寬度比例
        controls_tab_layout.addWidget(controls_splitter)
        self.preview_tab_widget.addTab(controls_tab_content_widget, "Controls JSON")

        # Procedures Tab
        procedures_tab_content_widget = QWidget()
        procedures_tab_layout = QVBoxLayout(procedures_tab_content_widget)
        procedures_tab_layout.setContentsMargins(0,0,0,0)
        procedures_splitter = QSplitter(Qt.Horizontal)
        self.procedures_list_view = QListView() # Lists selected document files
        self.procedures_list_view.setObjectName("proceduresListView")
        self.procedures_list_view.clicked.connect(self._on_procedure_doc_selected)
        procedures_splitter.addWidget(self.procedures_list_view)
        self.procedures_text_preview = QTextEdit() # Displays content of selected document
        self.procedures_text_preview.setReadOnly(True)
        self.procedures_text_preview.setObjectName("proceduresTextPreview")
        procedures_splitter.addWidget(self.procedures_text_preview)
        procedures_splitter.setSizes([200, 300])
        procedures_tab_layout.addWidget(procedures_splitter)
        self.preview_tab_widget.addTab(procedures_tab_content_widget, "Procedure Documents")

        # Evidences tab is no longer created.

        lay.addWidget(self.preview_container)

        # Compare button - Moved to bottom right
        self.btn_compare = QPushButton()  # Text set in _refresh
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        # Remove the setStyleSheet call below this line
        # self.btn_compare.setStyleSheet("""
        #     QPushButton {
        #         font-size: 15px;
        #         font-weight: 500;
        #         padding: 10px 24px;
        #         border-radius: 4px;
        #         color: white;
        #         background-color: #1a73e8;
        #         border: none;
        #         margin-top: 10px; 
        #         margin-bottom: 10px;
        #     }
        #     QPushButton:hover {
        #         background-color: #1765cc;
        #     }
        #     QPushButton:pressed {
        #         background-color: #1459b3;
        #     }
        #     QPushButton:disabled {
        #         background-color: #e0e0e0;
        #         color: #aaaaaa;
        #     }
        # """)
        
        # Create a container for the button to position it at the bottom right
        button_container = QWidget()
        button_container.setFixedHeight(60)  # 固定高度，預留空間
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()  # Add stretch to push button to the right
        button_layout.addWidget(self.btn_compare)
        
        # 將按鈕容器放在最底層
        lay.addStretch()  # 先加入 stretch 將按鈕推到底部
        lay.addWidget(button_container)

        # Connect toggle button
        self.toggle_preview_button.clicked.connect(self._toggle_preview_visibility)
        
        # Set initial state for preview area based on the instance variable
        self._update_preview_ui_state()

    # _handle_tree_selection is removed as QFileSystemModel is no longer the primary way to show file previews.
    # Instead, _update_controls_preview and _on_procedure_txt_selected handle content display.

    def _toggle_preview_visibility(self):
        self._preview_is_visible = not self._preview_is_visible
        self._update_preview_ui_state()

    def _update_preview_ui_state(self):
        self.preview_content_area.setVisible(self._preview_is_visible)
        if self._preview_is_visible:
            self.toggle_preview_button.setText("Hide File Preview")
        else:
            self.toggle_preview_button.setText("Show File Preview")

    # ---------- Helpers ----------
    # def _row(self, line, chooser): # _row helper is no longer needed in this form
    #     h = QHBoxLayout()
    #     h.addWidget(line)
    #     b = QPushButton("Browse…")
    #     b.setStyleSheet("""
    #         QPushButton {
    #             padding: 8px 12px; /* Match QLineEdit padding */
    #             background-color: #e9ecef; /* Light grayish blue */
    #             border: 1px solid #ced4da;
    #             border-radius: 4px;
    #             color: #495057;
    #             font-size: 14px;
    #             font-weight: 500;
    #         }
    #         QPushButton:hover {
    #             background-color: #dee2e6;
    #         }
    #         QPushButton:pressed {
    #             background-color: #ced4da;
    #         }
    #     """)
    #     b.clicked.connect(chooser)
    #     h.addWidget(b)
    #     return h

    def _tool_btn(self, icon, tip, slot):
        btn = QToolButton()
        btn.setIcon(self.style().standardIcon(icon))
        btn.setToolTip(tip)
        btn.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px; /* Smaller padding for icon buttons */
                border-radius: 12px; /* Half of width/height for circle (approx 24x24) */
                background-color: transparent;
                color: #5f6368; /* Google's standard icon color */
            }
            QToolButton:hover {
                background-color: #f0f0f0; /* Light gray for hover, adjust as needed */
            }
            QToolButton:pressed {
                background-color: #e0e0e0; /* Darker gray for pressed */
            }
        """)
        btn.setFixedSize(24, 24)  # Ensure circularity if padding is small
        btn.clicked.connect(slot)
        return btn

    # ---------- File/Folder Pickers and Validation ----------
    def _pick_ctrl(self):
        # Pick a single JSON file for controls
        start_dir = str(self.project.controls_json_path.parent if self.project.controls_json_path and self.project.controls_json_path.exists() else Path.home())
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Controls JSON File", start_dir, "JSON Files (*.json)")
        if file_path:
            self.project.controls_json_path = Path(file_path)
            self.project.changed.emit() # Triggers _refresh
            self._ctrl_edit.setFocus()
            # _update_controls_preview() will be called by _refresh

    def _validate_controls_json(self):
        if not self.project.controls_json_path or not self.project.controls_json_path.exists():
            QMessageBox.warning(self, "Validation Error", "Controls JSON file not selected or does not exist.")
            self.controls_json_preview.setText("Controls JSON file not selected or does not exist.")
            return

        try:
            with open(self.project.controls_json_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = json.loads(content)
        except FileNotFoundError:
            msg = f"File not found: {self.project.controls_json_path}"
            QMessageBox.critical(self, "Validation Error", msg)
            self.controls_json_preview.setText(msg)
            return
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON: {e}"
            QMessageBox.critical(self, "Validation Error", msg)
            self.controls_json_preview.setText(msg)
            return
        except Exception as e:
            msg = f"Error reading file: {e}"
            QMessageBox.critical(self, "Validation Error", msg)
            self.controls_json_preview.setText(msg)
            return

        # New simplified validation logic
        if not isinstance(data, dict):
            msg = "JSON must be an object."
            QMessageBox.critical(self, "Validation Error", msg)
            self.controls_json_preview.setText(msg)
            return

        if "name" not in data:
            msg = "Missing 'name' key in JSON."
            QMessageBox.critical(self, "Validation Error", msg)
            self.controls_json_preview.setText(msg)
            return

        if not isinstance(data["name"], str):
            msg = "'name' key must be a string."
            QMessageBox.critical(self, "Validation Error", msg)
            self.controls_json_preview.setText(msg)
            return

        for key, value in data.items():
            if key == "name":
                continue  # Already validated
            if not isinstance(value, str):
                msg = f"Value for key '{key}' must be a string."
                QMessageBox.critical(self, "Validation Error", msg)
                self.controls_json_preview.setText(msg)
                return

        success_msg = "Controls JSON structure is valid according to the new simplified schema."
        QMessageBox.information(self, "Validation Successful", success_msg)
        # Update preview with formatted JSON if valid, or success message
        try:
            formatted_json = json.dumps(data, indent=4, ensure_ascii=False)
            self.controls_json_preview.setText(formatted_json) # Show formatted JSON on success
        except Exception as e: # Should not happen if previous validation passed
             logger.error(f"Error formatting validated JSON for preview: {e}")
             self.controls_json_preview.setText(success_msg) # Fallback to success message
        # self._update_controls_preview() # Already called by _refresh after project.changed,
        # but direct update here gives immediate feedback on validation.

    def _pick_proc(self):
        # Pick multiple document files for procedures
        start_dir = str(Path.home())
        if self.project.procedure_doc_paths:
            first_valid_path = next((p for p in self.project.procedure_doc_paths if p.exists()), None)
            if first_valid_path:
                start_dir = str(first_valid_path.parent if first_valid_path.is_file() else first_valid_path)

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Procedure Documents", 
            start_dir, 
            "Text Files (*.txt);;Markdown Files (*.md);;All Files (*.*)"
        )
        if file_paths:
            self.project.procedure_doc_paths = [Path(fp) for fp in file_paths]
            self.project.changed.emit() # Triggers _refresh
            self._proc_edit.setFocus()
            # _update_procedures_preview() will be called by _refresh

    # _pick_evid and old _pick methods are removed.

    # ---------- Preview Update Methods ----------
    def _update_controls_preview(self):
        """更新 Controls 預覽區域的內容"""
        if self.project.controls_json_path and self.project.controls_json_path.exists():
            # 更新左側列表
            model = QStringListModel([self.project.controls_json_path.name])
            self.controls_list_view.setModel(model)
            
            # 更新右側內容
            try:
                with open(self.project.controls_json_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                parsed_json = json.loads(content)
                formatted_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
                self.controls_json_preview.setText(formatted_json)
            except Exception as e:
                self.controls_json_preview.setText(f"Error loading JSON: {e}")
        else:
            self.controls_list_view.setModel(QStringListModel([]))
            self.controls_json_preview.clear()

    def _update_procedures_preview(self):
        if self.project.procedure_doc_paths:
            model = QStringListModel([p.name for p in self.project.procedure_doc_paths])
            self.procedures_list_view.setModel(model)
        else:
            self.procedures_list_view.setModel(QStringListModel([]))
        self.procedures_text_preview.clear() # Clear text preview when list reloads

    def _on_procedure_doc_selected(self, index):
        # Display content of the selected document file
        if not self.project.procedure_doc_paths or not index.isValid():
            self.procedures_text_preview.clear()
            return

        selected_path_index = index.row()
        if 0 <= selected_path_index < len(self.project.procedure_doc_paths):
            doc_path = self.project.procedure_doc_paths[selected_path_index]
            try:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.procedures_text_preview.setText(content)
            except Exception as e:
                self.procedures_text_preview.setText(f"Error reading file: {e}")
        else:
            self.procedures_text_preview.clear()

    def _on_control_file_selected(self, index):
        """當選擇左側列表中的檔案時，在右側顯示其內容"""
        if not index.isValid():
            return
            
        file_path = self.project.controls_json_path
        if file_path and file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                parsed_json = json.loads(content)
                formatted_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
                self.controls_json_preview.setText(formatted_json)
            except Exception as e:
                self.controls_json_preview.setText(f"Error loading JSON: {e}")

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

        # Update path edits
        controls_path_str = str(self.project.controls_json_path or "")
        self._ctrl_edit.setText(controls_path_str)
        self.validate_json_button.setEnabled(bool(self.project.controls_json_path and self.project.controls_json_path.exists()))

        if self.project.procedure_doc_paths:
            if len(self.project.procedure_doc_paths) == 1:
                procedures_display_str = str(self.project.procedure_doc_paths[0])
            else:
                procedures_display_str = f"{len(self.project.procedure_doc_paths)} documents selected"
        else:
            procedures_display_str = ""
        self._proc_edit.setText(procedures_display_str)

        # evidences_path_str and self._evid_edit are removed.

        # Update Previews
        self._update_controls_preview()
        self._update_procedures_preview()
        # Evidences preview is removed.

        # QFileSystemModel logic is removed.
        # Old loop for tree views is removed.
        
        if self.project.is_sample:
            self.btn_compare.setText("Re-run sample")
            # 移除強制設定的樣式，讓主題系統接管
            # sample_style = f"""
            #     ProjectEditor {{
            #         background-color: {"#e3f2fd" if self.project.name == "ISO27k-A.9.4.2_強密碼合規稽核範例" else "#f1f8e9"};
            #         border-radius: 8px;
            #         border: 1px solid #dadce0;
            #     }}
            # """
            # self.setStyleSheet(sample_style)
        else:
            self.btn_compare.setText("Start compare")

        self.btn_compare.setEnabled(self.project.ready)
# --------------------------------------------------------------------
