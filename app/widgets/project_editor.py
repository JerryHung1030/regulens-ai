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
from app.utils.font_manager import get_font, get_display_font


class ProjectEditor(QWidget):
    """Folder picker + compare launcher."""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, translator, parent=None): # Added translator
        super().__init__(parent)
        self.project = project
        self.translator = translator # Store translator
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
        self.lb_title = QLabel() # Text set in _refresh
        self.lb_title.setFont(get_display_font(size=12))  # 設定標題字體
        head.addWidget(self.lb_title)
        
        # Tool buttons - Tooltips will be set in _retranslate_ui
        self.rename_button = self._tool_btn(QStyle.SP_FileDialogDetailedView, "", self._rename) # Placeholder tooltip
        self.delete_button = self._tool_btn(QStyle.SP_DialogDiscardButton, "", self._delete) # Placeholder tooltip
        head.addWidget(self.rename_button)
        head.addWidget(self.delete_button)
        head.addStretch()
        lay.addLayout(head)

        # Folder Selection Area
        self.folder_selection_container = QWidget()
        folder_selection_layout = QVBoxLayout(self.folder_selection_container)
        folder_selection_layout.setContentsMargins(0, 0, 0, 0)
        folder_selection_layout.setSpacing(10)

        self._ctrl_edit, self._proc_edit = [QLineEdit(readOnly=True) for _ in range(2)]
        for edit in [self._ctrl_edit, self._proc_edit]:
            edit.setFont(get_display_font(size=10))  # 設定輸入框字體

        # Controls Row
        controls_row_layout = QHBoxLayout()
        controls_row_layout.setAlignment(Qt.AlignVCenter)
        self.controls_label = QLabel() # Text set in _retranslate_ui
        self.controls_label.setObjectName("controls_json_file_label")
        self.controls_label.setFixedWidth(180)
        self.controls_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.controls_label.setFont(get_display_font(size=10))  # 設定標籤字體
        controls_row_layout.addWidget(self.controls_label)

        self.browse_ctrl_button = QPushButton() # Text set in _retranslate_ui
        self.browse_ctrl_button.setObjectName("controls_json_file_browse_button")
        self.browse_ctrl_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.browse_ctrl_button.clicked.connect(self._pick_ctrl)
        self.browse_ctrl_button.setFont(get_display_font(size=10))  # 設定按鈕字體
        controls_row_layout.addWidget(self.browse_ctrl_button)
        controls_row_layout.addWidget(self._ctrl_edit)
        
        self.validate_json_button = QPushButton() # Text set in _retranslate_ui
        self.validate_json_button.setObjectName("validate_json_button")
        self.validate_json_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.validate_json_button.clicked.connect(self._validate_controls_json)
        self.validate_json_button.setEnabled(False)
        self.validate_json_button.setFont(get_display_font(size=10))  # 設定按鈕字體
        controls_row_layout.addWidget(self.validate_json_button)
        folder_selection_layout.addLayout(controls_row_layout)

        # Procedures Row
        procedures_row_layout = QHBoxLayout()
        procedures_row_layout.setAlignment(Qt.AlignVCenter)
        self.procedures_label = QLabel() # Text set in _retranslate_ui
        self.procedures_label.setObjectName("procedure_doc_files_label")
        self.procedures_label.setFixedWidth(180)
        self.procedures_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.procedures_label.setFont(get_display_font(size=10))  # 設定標籤字體
        procedures_row_layout.addWidget(self.procedures_label)

        self.browse_proc_button = QPushButton() # Text set in _retranslate_ui
        self.browse_proc_button.setObjectName("procedure_doc_files_browse_button")
        self.browse_proc_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.browse_proc_button.clicked.connect(self._pick_proc)
        self.browse_proc_button.setFont(get_display_font(size=10))  # 設定按鈕字體
        procedures_row_layout.addWidget(self.browse_proc_button)
        procedures_row_layout.addWidget(self._proc_edit)
        folder_selection_layout.addLayout(procedures_row_layout)

        lay.addWidget(self.folder_selection_container)

        # File Preview Section
        self.preview_container = QWidget()
        self.preview_container.setObjectName("previewContainer")
        preview_container_layout = QVBoxLayout(self.preview_container)
        preview_container_layout.setContentsMargins(0, 10, 0, 0)

        self.toggle_preview_button = QPushButton() # Text set in _update_preview_ui_state (which calls _retranslate_ui implicitly)
        self.toggle_preview_button.setObjectName("togglePreviewButton")
        self.toggle_preview_button.setFont(get_display_font(size=10))  # 設定按鈕字體
        preview_container_layout.addWidget(self.toggle_preview_button)

        self.preview_content_area = QWidget()
        preview_content_layout = QVBoxLayout(self.preview_content_area)
        preview_content_layout.setContentsMargins(0, 5, 0, 0)
        preview_container_layout.addWidget(self.preview_content_area)

        self.preview_tab_widget = QTabWidget()
        self.preview_tab_widget.setObjectName("previewTabWidget")
        self.preview_tab_widget.setFont(get_display_font(size=10))  # 設定分頁字體
        preview_content_layout.addWidget(self.preview_tab_widget)

        # Controls Tab
        self.controls_tab_content_widget = QWidget()
        controls_tab_layout = QVBoxLayout(self.controls_tab_content_widget)
        controls_tab_layout.setContentsMargins(0,0,0,0)
        controls_splitter = QSplitter(Qt.Horizontal)
        self.controls_list_view = QListView()
        self.controls_list_view.setObjectName("controlsListView")
        self.controls_list_view.clicked.connect(self._on_control_file_selected)
        self.controls_list_view.setFont(get_display_font(size=10))  # 設定列表字體
        controls_splitter.addWidget(self.controls_list_view)
        self.controls_json_preview = QTextEdit()
        self.controls_json_preview.setReadOnly(True)
        self.controls_json_preview.setObjectName("controlsJsonPreview")
        self.controls_json_preview.setFont(get_display_font(size=10))  # 設定預覽字體
        controls_splitter.addWidget(self.controls_json_preview)
        controls_splitter.setSizes([200, 300])
        controls_tab_layout.addWidget(controls_splitter)

        # Procedures Tab
        self.procedures_tab_content_widget = QWidget()
        procedures_tab_layout = QVBoxLayout(self.procedures_tab_content_widget)
        procedures_tab_layout.setContentsMargins(0,0,0,0)
        procedures_splitter = QSplitter(Qt.Horizontal)
        self.procedures_list_view = QListView()
        self.procedures_list_view.setObjectName("proceduresListView")
        self.procedures_list_view.clicked.connect(self._on_procedure_doc_selected)
        self.procedures_list_view.setFont(get_display_font(size=10)) # Apply display font to list view
        procedures_splitter.addWidget(self.procedures_list_view)
        self.procedures_text_preview = QTextEdit()
        self.procedures_text_preview.setReadOnly(True)
        self.procedures_text_preview.setObjectName("proceduresTextPreview")
        # Use get_display_font for general text preview
        self.procedures_text_preview.setFont(get_display_font(size=10)) 
        procedures_splitter.addWidget(self.procedures_text_preview)
        procedures_splitter.setSizes([200, 300])
        procedures_tab_layout.addWidget(procedures_splitter)

        lay.addWidget(self.preview_container)

        # Compare button
        self.btn_compare = QPushButton()  # Text set in _refresh (which calls _retranslate_ui implicitly)
        self.btn_compare.setObjectName("btnCompare") # Set object name for QSS styling
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        self.btn_compare.setFont(get_display_font(size=12))  # 設定按鈕字體
        
        button_container = QWidget()
        button_container.setFixedHeight(60)
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_compare)
        
        lay.addStretch()
        lay.addWidget(button_container)

        self.toggle_preview_button.clicked.connect(self._toggle_preview_visibility)
        
        self._update_preview_ui_state() # This will also call _retranslate_ui for button text
        
        # Connect translator for dynamic updates
        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui() # Initial translation

    def _retranslate_ui(self):
        # Update tooltips
        self.rename_button.setToolTip(self.translator.get("project_editor_rename_tooltip", "Rename project"))
        self.delete_button.setToolTip(self.translator.get("project_editor_delete_tooltip", "Delete project"))

        # Update labels and apply fonts
        self.controls_label.setText(self.translator.get("project_editor_controls_json_label", "Controls JSON File:"))
        self.controls_label.setFont(get_display_font(size=10))
        self.procedures_label.setText(self.translator.get("project_editor_procedure_docs_label", "Procedure Documents:"))
        self.procedures_label.setFont(get_display_font(size=10))

        # Update button texts and apply fonts
        self.browse_ctrl_button.setText(self.translator.get("project_editor_browse_button", "Browse…"))
        self.browse_ctrl_button.setFont(get_display_font(size=10))
        self.browse_proc_button.setText(self.translator.get("project_editor_browse_button", "Browse…"))
        self.browse_proc_button.setFont(get_display_font(size=10))
        self.validate_json_button.setText(self.translator.get("project_editor_validate_json_button", "Validate JSON"))
        self.validate_json_button.setFont(get_display_font(size=10))
        
        # Update toggle preview button text (also handled in _update_preview_ui_state) and apply font
        if self._preview_is_visible:
            self.toggle_preview_button.setText(self.translator.get("project_editor_hide_preview_button", "Hide File Preview"))
        else:
            self.toggle_preview_button.setText(self.translator.get("project_editor_show_preview_button", "Show File Preview"))
        self.toggle_preview_button.setFont(get_display_font(size=10))

        # Update tab titles and apply font to tab bar
        self.preview_tab_widget.setFont(get_display_font(size=10)) # Sets font for the tab text
        current_tab_count = self.preview_tab_widget.count()
        if current_tab_count == 0 : # Add tabs only if they don't exist
            self.preview_tab_widget.addTab(self.controls_tab_content_widget, self.translator.get("project_editor_controls_tab", "Controls JSON"))
            self.preview_tab_widget.addTab(self.procedures_tab_content_widget, self.translator.get("project_editor_procedures_tab", "Procedure Documents"))
        else: # Update existing tab titles
            self.preview_tab_widget.setTabText(0, self.translator.get("project_editor_controls_tab", "Controls JSON"))
            if current_tab_count > 1: # Check if procedure tab exists before trying to set text
                 self.preview_tab_widget.setTabText(1, self.translator.get("project_editor_procedures_tab", "Procedure Documents"))

        # Refresh texts that depend on project state (like compare button)
        self._refresh_dynamic_texts() # This will also apply fonts to elements within it
        logger.debug("ProjectEditor UI retranslated")

    def _refresh_dynamic_texts(self):
        # This method is for texts that change based on project state AND need translation
        # For example, the compare button text
        self.lb_title.setText(f"<h2>{self.project.name}</h2>") # Project name is not translated
        self.lb_title.setFont(get_display_font(size=16, weight_style='semi_bold'))

        if self.project.is_sample:
            self.btn_compare.setText(self.translator.get("project_editor_rerun_sample_button", "Re-run sample"))
        else:
            self.btn_compare.setText(self.translator.get("project_editor_start_compare_button", "Start compare"))
        self.btn_compare.setFont(get_display_font(size=11, weight_style='semi_bold'))
        
        # Update procedure edit text for multiple files
        if self.project.procedure_doc_paths and len(self.project.procedure_doc_paths) > 1:
            self._proc_edit.setText(self.translator.get("project_editor_multiple_docs_selected", "{count} documents selected").format(count=len(self.project.procedure_doc_paths)))
        elif self.project.procedure_doc_paths and len(self.project.procedure_doc_paths) == 1:
            self._proc_edit.setText(str(self.project.procedure_doc_paths[0]))
        else:
            self._proc_edit.setText("")
        # Font for _proc_edit is set in _refresh, after this method is called.


    def _toggle_preview_visibility(self):
        self._preview_is_visible = not self._preview_is_visible
        self._update_preview_ui_state()

    def _update_preview_ui_state(self):
        self.preview_content_area.setVisible(self._preview_is_visible)
        # This will call _retranslate_ui, which updates the button text and applies its font
        if self._preview_is_visible:
            self.toggle_preview_button.setText(self.translator.get("project_editor_hide_preview_button", "Hide File Preview"))
        else:
            self.toggle_preview_button.setText(self.translator.get("project_editor_show_preview_button", "Show File Preview"))
        # Font for toggle_preview_button is set in _retranslate_ui

    # ---------- Helpers ----------
    # def _row(self, line, chooser):
    #     h.addWidget(line)
    #     b = QPushButton("Browse…") # This would need translation too if used
    #     # ... styles ...
    #     b.clicked.connect(chooser)
    #     h.addWidget(b)
    #     return h

    def _tool_btn(self, icon, tip_key, slot): # Changed tip to tip_key
        btn = QToolButton()
        btn.setIcon(self.style().standardIcon(icon))
        # Tooltip set by _retranslate_ui using tip_key if it's stored, or directly if not dynamic
        # For simplicity, if these tooltips are static, they are set in _retranslate_ui
        # If they need to be dynamic based on `tip_key`, then this method needs the translator
        # or the caller needs to handle it. Assuming static for now, set in _retranslate_ui.
        # btn.setToolTip(self.translator.get(tip_key, default_tip_value_if_any))
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
        # TODO: Internationalize QMessageBox messages and preview text messages
        # This requires defining keys and using self.translator.get()
        # Example for one message:
        # title = self.translator.get("validation_error_title", "Validation Error")
        # text = self.translator.get("controls_json_not_selected_text", "Controls JSON file not selected or does not exist.")
        # QMessageBox.warning(self, title, text)
        # self.controls_json_preview.setText(text)

        if not self.project.controls_json_path or not self.project.controls_json_path.exists():
            title = self.translator.get("validation_error_title", "Validation Error")
            text = self.translator.get("controls_json_not_selected_text", "Controls JSON file not selected or does not exist.")
            QMessageBox.warning(self, title, text)
            self.controls_json_preview.setText(text)
            return

        try:
            with open(self.project.controls_json_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = json.loads(content)
        except FileNotFoundError:
            msg = self.translator.get("file_not_found_error", "File not found: {path}").format(path=self.project.controls_json_path)
            QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
            self.controls_json_preview.setText(msg)
            return
        except json.JSONDecodeError as e:
            msg = self.translator.get("json_decode_error", "The file '{filename}' is not a valid JSON file. Please check its format.\n\nDetails: {error_details}").format(filename=self.project.controls_json_path.name, error_details=e)
            QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
            self.controls_json_preview.setText(msg)
            return
        except Exception as e:
            msg = self.translator.get("file_read_error", "Error reading file '{filename}'.\n\nDetails: {error_details}").format(filename=self.project.controls_json_path.name, error_details=e)
            QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
            self.controls_json_preview.setText(msg)
            return

        if not isinstance(data, dict):
            msg = self.translator.get("json_must_be_object_error", "The controls JSON file '{filename}' must be an object (dictionary).").format(filename=self.project.controls_json_path.name)
            QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
            self.controls_json_preview.setText(msg)
            return

        if "name" not in data:
            msg = self.translator.get("json_missing_name_key_error", "The controls JSON file '{filename}' is missing the 'name' key.").format(filename=self.project.controls_json_path.name)
            QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
            self.controls_json_preview.setText(msg)
            return

        if not isinstance(data["name"], str):
            msg = self.translator.get("json_name_must_be_string_error", "In '{filename}', the 'name' key must correspond to a string value.").format(filename=self.project.controls_json_path.name)
            QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
            self.controls_json_preview.setText(msg)
            return

        for key, value in data.items():
            if key == "name":
                continue
            if not isinstance(value, str):
                msg = self.translator.get("json_value_must_be_string_error", "In '{filename}', the value for key '{key_name}' must be a string.").format(filename=self.project.controls_json_path.name, key_name=key)
                QMessageBox.critical(self, self.translator.get("validation_error_title", "Validation Error"), msg)
                self.controls_json_preview.setText(msg)
                return
        
        success_title = self.translator.get("validation_successful_title", "Validation Successful")
        success_msg = self.translator.get("json_valid_schema_message", "Controls JSON structure is valid according to the new simplified schema.")
        QMessageBox.information(self, success_title, success_msg)
        try:
            formatted_json = json.dumps(data, indent=4, ensure_ascii=False)
            self.controls_json_preview.setText(formatted_json)
        except Exception as e:
             logger.error(f"Error formatting validated JSON for preview: {e}")
             self.controls_json_preview.setText(success_msg)


    def _pick_proc(self):
        start_dir = str(Path.home())
        if self.project.procedure_doc_paths:
            first_valid_path = next((p for p in self.project.procedure_doc_paths if p.exists()), None)
            if first_valid_path:
                start_dir = str(first_valid_path.parent if first_valid_path.is_file() else first_valid_path)
        
        dialog_title = self.translator.get("select_procedure_docs_dialog_title", "Select Procedure Documents")
        file_filter = self.translator.get("text_files_filter", "Text Files (*.txt)") + ";;" + \
                      self.translator.get("markdown_files_filter", "Markdown Files (*.md)") + ";;" + \
                      self.translator.get("all_files_filter", "All Files (*.*)")


        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            dialog_title, 
            start_dir, 
            file_filter
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
                self.procedures_text_preview.setText(self.translator.get("error_reading_file_preview", "Error reading file: {error}").format(error=e))
        else:
            self.procedures_text_preview.clear()

    def _on_control_file_selected(self, index):
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
                self.controls_json_preview.setText(self.translator.get("error_loading_json_preview", "Error loading JSON: {error}").format(error=e))

    # ---------- Project operations ----------
    def _rename(self):
        title = self.translator.get("rename_project_dialog_title", "Rename project")
        label = self.translator.get("rename_project_dialog_label", "New name:")
        new, ok = QInputDialog.getText(self, title, label, text=self.project.name)
        if ok and new: 
            self.project.rename(new) # project.name is not translated itself
            
    def _delete(self):
        title = self.translator.get("delete_project_dialog_title", "Delete project")
        text = self.translator.get("delete_project_dialog_text", 'Delete "{project_name}"?').format(project_name=self.project.name)
        if QMessageBox.question(self, title, text) == QMessageBox.Yes:
            self.project.deleted.emit()

    # ---------- Refresh ----------
    def _refresh(self):
        # This calls _retranslate_ui through _refresh_dynamic_texts
        self._retranslate_ui() 

        # Update path edits (these are file paths, not typically translated) and apply fonts
        controls_path_str = str(self.project.controls_json_path or "")
        self._ctrl_edit.setText(controls_path_str)
        self._ctrl_edit.setFont(get_display_font(size=10))
        self.validate_json_button.setEnabled(bool(self.project.controls_json_path and self.project.controls_json_path.exists()))

        # _refresh_dynamic_texts handles the procedure edit text for multiple files.
        # Apply font to _proc_edit here, as its text content might have been updated by _refresh_dynamic_texts (called by _retranslate_ui above)
        self._proc_edit.setFont(get_display_font(size=10))

        # Update Previews
        # Fonts for preview panes (controls_json_preview, procedures_text_preview) and 
        # list views (controls_list_view, procedures_list_view) are set in _build_ui.
        self._update_controls_preview()
        self._update_procedures_preview()
        
        self.btn_compare.setEnabled(self.project.ready)
# --------------------------------------------------------------------
