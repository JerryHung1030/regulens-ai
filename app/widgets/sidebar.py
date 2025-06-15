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
from app.utils.font_manager import get_font  # 新增字體管理器導入
from app.logger import logger  # 新增 logger 導入


class Sidebar(QWidget):
    project_selected = Signal(CompareProject)
    add_project_requested = Signal()
    toggled = Signal()

    def __init__(self, project_store: ProjectStore, splitter: QSplitter, translator, parent: QWidget | None = None): # Added translator
        super().__init__(parent)
        self.project_store = project_store
        self._splitter = splitter
        self.translator = translator # Store translator
        self.COLLAPSED_WIDTH = 60

        self.list_projects = QListWidget()
        self.list_projects.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_projects.setTextElideMode(Qt.ElideRight)
        # 設定列表字體
        self.list_projects.setFont(get_font('regular', 10))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)  # Consistent spacing

        # Top row for buttons
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(2)

        # Toggle Button
        self._btn_toggle = QToolButton()  # Create the button before using it
        self._btn_toggle.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 6px; /* Slightly increased padding */
                border-radius: 4px;
                background-color: transparent; /* Make background transparent initially */
            }
            QToolButton:hover {
                background-color: #dddddd; /* Slightly darker gray for hover */
            }
            QToolButton:pressed {
                background-color: #cccccc; /* Even darker for pressed state */
            }
        """)
        self._btn_toggle.clicked.connect(self._toggle)
        top_row_layout.addWidget(self._btn_toggle)
        
        # Set initial icon and tooltip based on splitter state (defaulting to expanded) - Handled by setup_initial_toggle_state / _retranslate_ui
        # self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        # self._btn_toggle.setToolTip("Collapse sidebar")

        # Add project button
        self.btn_add_project = QToolButton()
        # self.btn_add_project.setText("＋") # Set in _retranslate_ui
        # self.btn_add_project.setToolTip("Create a new project") # Set in _retranslate_ui
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
        # 設定按鈕字體
        self.btn_add_project.setFont(get_font('regular', 16))
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
        # Update toggle button tooltip based on current state
        if not self.list_projects.isVisible() or (self._splitter.sizes() and self._splitter.sizes()[0] == self.COLLAPSED_WIDTH):
            self._btn_toggle.setToolTip(self.translator.get("sidebar_expand_tooltip", "Expand sidebar"))
        else:
            self._btn_toggle.setToolTip(self.translator.get("sidebar_collapse_tooltip", "Collapse sidebar"))
        
        self.btn_add_project.setText(self.translator.get("sidebar_add_project_button", "＋"))
        self.btn_add_project.setToolTip(self.translator.get("sidebar_add_project_tooltip", "Create a new project"))
        
        # Refresh project list to update sample tags if language changed
        self.refresh_project_list()
        logger.debug("Sidebar UI retranslated")

    def setup_initial_toggle_state(self):
        if not self._splitter or not self._splitter.sizes():
            return

        initial_width = self._splitter.sizes()[0]
        if initial_width <= self.COLLAPSED_WIDTH:
            self.list_projects.hide()
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self._btn_toggle.setToolTip(self.translator.get("sidebar_expand_tooltip", "Expand sidebar"))
            current_sizes = self._splitter.sizes()
            if len(current_sizes) > 1 and current_sizes[0] != self.COLLAPSED_WIDTH:
                self._splitter.setSizes([self.COLLAPSED_WIDTH, current_sizes[1]])
            self.setMinimumWidth(self.COLLAPSED_WIDTH)
        else:
            self.list_projects.show()
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
            self._btn_toggle.setToolTip(self.translator.get("sidebar_collapse_tooltip", "Collapse sidebar"))
            self.setMinimumWidth(200)

    def _toggle(self):
        current_width = self._splitter.sizes()[0]
        current_sizes = self._splitter.sizes()

        if not self.list_projects.isVisible() or current_width == self.COLLAPSED_WIDTH:
            expanded_width = self._splitter.property("last_expanded_width") or 220
            self.list_projects.show()
            if len(current_sizes) > 1: current_sizes[0] = expanded_width
            else: current_sizes = [expanded_width, 0] 
            self._splitter.setSizes(current_sizes)
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
            self._btn_toggle.setToolTip(self.translator.get("sidebar_collapse_tooltip", "Collapse sidebar"))
            self.setMinimumWidth(200)
        else:
            self._splitter.setProperty("last_expanded_width", current_width)
            self.list_projects.hide()
            if len(current_sizes) > 1: current_sizes[0] = self.COLLAPSED_WIDTH
            else: current_sizes = [self.COLLAPSED_WIDTH, 0]
            self._splitter.setSizes(current_sizes)
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self._btn_toggle.setToolTip(self.translator.get("sidebar_expand_tooltip", "Expand sidebar"))
            self.setMinimumWidth(self.COLLAPSED_WIDTH)
        self.toggled.emit()

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
                if proj.name == "ISO27k-A.9.4.2_強密碼合規稽核範例":
                    prefix_tag = sample_tag_blue
                elif proj.name == "ISO27k-A.6.1.2_風險清冊稽核範例":
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
