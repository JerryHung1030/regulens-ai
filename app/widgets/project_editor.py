# ---------- Reference ProjectEditor (drop-in replacement) ----------
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QDir
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QToolButton, QFileDialog, QInputDialog, QMessageBox,
    QStyle, QTreeView, QTextEdit, QTabWidget, QSplitter, QFileSystemModel, QSizePolicy
)
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

        # Initialize QFileSystemModels
        self.controls_fs_model = QFileSystemModel()
        self.controls_fs_model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)
        self.controls_fs_model.setRootPath(QDir.homePath())  # Placeholder

        self.procedures_fs_model = QFileSystemModel()
        self.procedures_fs_model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)
        self.procedures_fs_model.setRootPath(QDir.homePath())  # Placeholder

        self.evidences_fs_model = QFileSystemModel()
        self.evidences_fs_model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)
        self.evidences_fs_model.setRootPath(QDir.homePath())  # Placeholder

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

        self._ctrl_edit, self._proc_edit, self._evid_edit = [QLineEdit(readOnly=True) for _ in range(3)]
        
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
        for edit_widget in [self._ctrl_edit, self._proc_edit, self._evid_edit]:
            # Remove the setStyleSheet call below this line
            pass # Keep pass or other logic if needed after removing setStyleSheet

        folder_configs = [
            ("Controls Folder:", self._ctrl_edit, self._pick_ctrl),
            ("Procedures Folder:", self._proc_edit, self._pick_proc),
            ("Evidences Folder:", self._evid_edit, self._pick_evid),
        ]

        for label_text, line_edit_widget, pick_slot in folder_configs:
            row_layout = QHBoxLayout()
            # Set vertical alignment for the row layout
            row_layout.setAlignment(Qt.AlignVCenter)
            label = QLabel(label_text)
            label.setObjectName(f"{label_text.replace(' ', '_').lower()}_label")
            # Set fixed width for the label to ensure alignment
            label.setFixedWidth(180)  # 設定固定寬度
            # Set fixed vertical size policy for QLabel
            label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            row_layout.addWidget(label)
            
            browse_button = QPushButton("Browse…")
            # Remove the setStyleSheet call below this line
            # browse_button.setStyleSheet("""
            #     QPushButton {
            #         font-size: 14px;
            #         padding: 8px 15px;
            #         border-radius: 4px;
            #         color: #1a73e8;
            #         border: 1px solid #dadce0;
            #         background-color: #ffffff;
            #     }
            #     QPushButton:hover {
            #         background-color: #f1f8ff;
            #         border-color: #1a73e8;
            #     }
            #     QPushButton:pressed {
            #         background-color: #e8f0fe;
            #     }
            # """)
            browse_button.setObjectName(f"{label_text.replace(' ', '_').lower()}_browse_button")
            # Set fixed vertical size policy for QPushButton
            browse_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            browse_button.clicked.connect(pick_slot)
            # Add browse_button before line_edit_widget for tab order
            row_layout.addWidget(browse_button)
            row_layout.addWidget(line_edit_widget)  # Add line_edit_widget after browse_button
            folder_selection_layout.addLayout(row_layout)
        
        # Set explicit tab order between browse buttons and their line edits if needed,
        # but the addWidget order change should handle it for within the row.
        # Example for inter-row or more complex scenarios:
        # QWidget.setTabOrder(self.controls_browse_button, self._ctrl_edit) 
        # QWidget.setTabOrder(self._ctrl_edit, self.procedures_browse_button)
        # For now, relying on addWidget order.

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

        # Create tabs
        folder_types = {
            "Controls": ("controls_tree_view", "controls_text_preview", "Controls Files"),
            "Procedures": ("procedures_tree_view", "procedures_text_preview", "Procedures Files"),
            "Evidences": ("evidences_tree_view", "evidences_text_preview", "Evidences Files"),
        }

        for key, (tree_attr, text_attr, tab_label) in folder_types.items():
            tab_content_widget = QWidget()
            tab_layout = QVBoxLayout(tab_content_widget)
            tab_layout.setContentsMargins(0, 0, 0, 0)

            splitter = QSplitter(Qt.Horizontal)

            # Left side: Tree View
            tree_view = QTreeView()
            setattr(self, tree_attr, tree_view)  # e.g., self.controls_tree_view = tree_view
            tree_view.setObjectName(tree_attr)  # e.g., self.controls_tree_view.setObjectName("controlsTreeView")
            
            current_model = None

            if key == "Controls":
                current_model = self.controls_fs_model
            elif key == "Procedures":
                current_model = self.procedures_fs_model
            elif key == "Evidences":
                current_model = self.evidences_fs_model
            
            if current_model:
                tree_view.setModel(current_model)
                tree_view.setHeaderHidden(True)
                for i in range(1, current_model.columnCount()):
                    tree_view.hideColumn(i)
            
            splitter.addWidget(tree_view)

            # Right side: Text Preview
            text_preview = QTextEdit()
            text_preview.setReadOnly(True)
            setattr(self, text_attr, text_preview)  # e.g., self.controls_text_preview = text_preview
            text_preview.setObjectName(text_attr)  # e.g., self.controls_text_preview.setObjectName("controlsTextPreview")
            splitter.addWidget(text_preview)
            
            # Connect selection changed signal
            if key == "Controls":
                tree_view.selectionModel().selectionChanged.connect(
                    lambda s, d, model=self.controls_fs_model, tp=self.controls_text_preview: 
                    self._handle_tree_selection(s, d, model, tp)
                )
            elif key == "Procedures":
                tree_view.selectionModel().selectionChanged.connect(
                    lambda s, d, model=self.procedures_fs_model, tp=self.procedures_text_preview: 
                    self._handle_tree_selection(s, d, model, tp)
                )
            elif key == "Evidences":
                tree_view.selectionModel().selectionChanged.connect(
                    lambda s, d, model=self.evidences_fs_model, tp=self.evidences_text_preview: 
                    self._handle_tree_selection(s, d, model, tp)
                )

            splitter.setSizes([150, 350])  # Initial sizes (30% tree, 70% text approx)
            tab_layout.addWidget(splitter)
            self.preview_tab_widget.addTab(tab_content_widget, tab_label)

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

    def _handle_tree_selection(self, selected, deselected, model: QFileSystemModel, text_preview: QTextEdit):
        indexes = selected.indexes()
        if indexes:
            index = indexes[0]
            file_path = model.filePath(index)
            if model.fileInfo(index).isFile():
                try:
                    # Attempt to decode with UTF-8, then fallback to others if needed
                    content = ""
                    for encoding in ['utf-8', 'latin-1', 'cp1252']:  # Common encodings
                        try:
                            with open(file_path, 'r', encoding=encoding) as f:
                                content = f.read()
                            break  # Successfully read
                        except UnicodeDecodeError:
                            logger.warning(f"File {file_path} failed to decode with {encoding}")
                            content = f"Error reading file: Could not decode with {encoding} or other tried encodings."
                        except Exception as e_read:  # Catch other read errors like permission denied
                            logger.error(f"Error reading file {file_path} with encoding {encoding}: {e_read}")
                            content = f"Error reading file: {e_read}"
                            break 
                    text_preview.setText(content)
                except Exception as e:  # General exception for file operations
                    logger.error(f"Failed to open or read file {file_path}: {e}")
                    text_preview.setText(f"Error opening or reading file: {e}")
            else:  # It's a directory
                text_preview.clear()
        else:  # No selection
            text_preview.clear()

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
            if edit:  # 'edit' is the QLineEdit associated with this picker
                edit.setFocus()  # Set focus to the line edit as a visual cue

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
        controls_path_str = str(self.project.controls_dir or "")
        procedures_path_str = str(self.project.procedures_dir or "")
        evidences_path_str = str(self.project.evidences_dir or "")

        self._ctrl_edit.setText(controls_path_str)
        self._proc_edit.setText(procedures_path_str)
        self._evid_edit.setText(evidences_path_str)

        # Update FileSystemModels and TreeViews
        self.controls_fs_model.setRootPath(controls_path_str if controls_path_str else QDir.homePath())
        self.controls_tree_view.setRootIndex(self.controls_fs_model.index(controls_path_str))
        self.controls_text_preview.clear()

        self.procedures_fs_model.setRootPath(procedures_path_str if procedures_path_str else QDir.homePath())
        self.procedures_tree_view.setRootIndex(self.procedures_fs_model.index(procedures_path_str))
        self.procedures_text_preview.clear()

        self.evidences_fs_model.setRootPath(evidences_path_str if evidences_path_str else QDir.homePath())
        self.evidences_tree_view.setRootIndex(self.evidences_fs_model.index(evidences_path_str))
        self.evidences_text_preview.clear()
        
        # For tree views, ensure columns are hidden after model reset if necessary
        # This might be redundant if setModel doesn't reset column visibility, but safe to include.
        for tv, model in [
            (self.controls_tree_view, self.controls_fs_model),
            (self.procedures_tree_view, self.procedures_fs_model),
            (self.evidences_tree_view, self.evidences_fs_model)
        ]:
            tv.setHeaderHidden(True)  # Re-apply in case it was reset
            for i in range(1, model.columnCount()):
                tv.hideColumn(i)

        if self.project.is_sample:
            self.btn_compare.setText("Re-run sample")
            # For sample projects, we might want a slightly different overall card style
            # The self.setStyleSheet below will override the _base_css for the ProjectEditor itself.
            sample_style = f"""
                ProjectEditor {{
                    background-color: {"#e3f2fd" if self.project.name == "ISO27k-A.9.4.2_強密碼合規稽核範例" else "#f1f8e9"};
                    border-radius: 8px;
                    border: 1px solid #dadce0; /* Keep consistent border */
                    /* Consider adding a subtle dashed border on top or left for distinction if needed */
                    /* border-top: 2px dashed #1a73e8; */
                }}
            """
            self.setStyleSheet(sample_style)
        else:
            self.btn_compare.setText("Start compare")
            # Remove the setStyleSheet call below this line
            # self.setStyleSheet(self._base_css)  # Apply the base style for non-sample projects

        self.btn_compare.setEnabled(self.project.ready)
# --------------------------------------------------------------------
