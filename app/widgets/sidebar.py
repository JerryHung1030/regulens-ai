from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QToolButton,
    QListWidgetItem,
    QSplitter,
    QStyle,
)
from PySide6.QtCore import Signal, Qt

from app.stores.project_store import ProjectStore
from app.models.project import CompareProject
from app.utils.font_manager import get_font, get_display_font  # 新增字體管理器導入
from app.logger import logger  # 新增 logger 導入


class Sidebar(QWidget):
    project_selected = Signal(CompareProject)
    add_project_requested = Signal()

    def __init__(self, project_store: ProjectStore, splitter: QSplitter, translator, parent: QWidget | None = None): # Added translator
        super().__init__(parent)
        self.project_store = project_store
        self._splitter = splitter
        self.translator = translator # Store translator

        self.list_projects = QListWidget()
        self.list_projects.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_projects.setTextElideMode(Qt.ElideRight)
        # 設定列表字體
        self.list_projects.setFont(get_display_font(size=10))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)  # Consistent spacing

        # Top row for buttons
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(2)

        # Add project button
        self.btn_add_project = QToolButton()
        self.btn_add_project.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 6px; /* Consistent padding */
                border-radius: 4px;
                font-size: 16px; /* Keep font size as is */
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: #dddddd;
            }
            QToolButton:pressed {
                background-color: #cccccc;
            }
        """)
        self.btn_add_project.setFont(get_display_font(size=16))  # 設定按鈕字體
        self.btn_add_project.clicked.connect(self.add_project_requested.emit)
        top_row_layout.addWidget(self.btn_add_project)
        top_row_layout.addStretch(1)  # Push buttons to the left

        main_layout.addLayout(top_row_layout)
        main_layout.addWidget(self.list_projects)

        self.list_projects.itemClicked.connect(self._on_project_clicked)
        self.project_store.changed.connect(self.refresh_project_list)
        
        self.setMinimumWidth(200) # Default expanded width

        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui() # Initial translation
        self.refresh_project_list() # Initial population

    def _retranslate_ui(self):
        self.btn_add_project.setText(self.translator.get("sidebar_add_project_button", "＋"))
        self.btn_add_project.setToolTip(self.translator.get("sidebar_add_project_tooltip", "Create a new project"))
        
        # Refresh project list to update sample tags if language changed
        self.refresh_project_list()
        logger.debug("Sidebar UI retranslated")

    def _on_project_clicked(self, item: QListWidgetItem):
        project = item.data(Qt.UserRole) 
        if isinstance(project, CompareProject):
            self.project_selected.emit(project)

    def refresh_project_list(self):
        current_project_data = None
        if self.list_projects.currentItem():
            current_project_data = self.list_projects.currentItem().data(Qt.UserRole)

        self.list_projects.clear()
        new_current_item = None
        
        # Get translated "SAMPLE" tag
        sample_tag_blue = f"<font color='#1565c0'>{self.translator.get('sidebar_sample_tag', 'SAMPLE')}</font>&nbsp;"
        sample_tag_green = f"<font color='#2e7d32'>{self.translator.get('sidebar_sample_tag', 'SAMPLE')}</font>&nbsp;"
        sample_tag_gray = f"<font color='gray'>{self.translator.get('sidebar_sample_tag', 'SAMPLE')}</font>&nbsp;"

        for proj in self.project_store.projects:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, proj)
            text_to_set = proj.name # Project name itself is not translated
            if proj.is_sample:
                prefix_tag = ""
                # These specific project names are identifiers, not for translation
                if proj.name == "資通安全實地稽核案例 (Demo)":
                    prefix_tag = sample_tag_green
                elif proj.name == "符合規範案例 (Demo)":
                    prefix_tag = sample_tag_green
                elif proj.name == "不符合規範案例 (Demo)":
                    prefix_tag = sample_tag_green
                else:
                    prefix_tag = sample_tag_gray
                text_to_set = prefix_tag + proj.name
            
            # QListWidgetItem itself doesn't directly support rich text for its main text.
            # To show HTML, you typically need to use a QLabel as the item widget.
            # However, for simplicity and if basic HTML like <font> is supported by the style/delegate,
            # setting text directly might work in some Qt configurations or with custom delegates.
            # For robust HTML, setItemWidget is preferred.
            # For now, we assume direct text setting handles basic HTML or it's styled otherwise.
            item.setText(text_to_set) 
            item.setData(Qt.DisplayRole, proj.name) # Store plain name for searching/editing
            self.list_projects.addItem(item)

            if current_project_data == proj:
                new_current_item = item
        
        if new_current_item:
            self.list_projects.setCurrentItem(new_current_item)
        elif self.list_projects.count() > 0:
            self.list_projects.setCurrentRow(0)
            first_item_project = self.list_projects.item(0).data(Qt.UserRole)
            if isinstance(first_item_project, CompareProject):
                self.project_selected.emit(first_item_project)
        else:
            pass
