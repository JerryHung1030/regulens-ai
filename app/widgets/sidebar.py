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


class Sidebar(QWidget):
    project_selected = Signal(CompareProject)
    add_project_requested = Signal()
    toggled = Signal()

    def __init__(self, project_store: ProjectStore, splitter: QSplitter, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_store = project_store
        self._splitter = splitter
        self.COLLAPSED_WIDTH = 60  # Define this as a class or local constant

        # Ensure list_projects is defined as early as possible
        self.list_projects = QListWidget()
        self.list_projects.setStyleSheet("""
            QListWidget {
                border: 1px solid #cccccc; /* Light gray border for the list itself */
                background-color: #ffffff; /* White background for the list area */
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px; /* Increased padding for items */
                border-radius: 4px; /* Subtle rounded corners for items */
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #e6f2ff; /* Light blue hover */
                color: #222222; /* Darker text on hover */
            }
            QListWidget::item:selected {
                background-color: #cce5ff; /* Slightly darker blue for selection */
                color: #000000; /* Black text for selected item for clarity */
                /* Optionally, add a border for selected item if needed */
                /* border-left: 3px solid #007bff; */
            }
        """)

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
        
        # Set initial icon and tooltip based on splitter state (defaulting to expanded)
        self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self._btn_toggle.setToolTip("Collapse sidebar")
        # The actual state will be set by setup_initial_toggle_state() called from Workspace

        # Add project button
        self.btn_add_project = QToolButton()
        self.btn_add_project.setText("＋")  # More compact for a top bar
        self.btn_add_project.setToolTip("Create a new project")
        self.btn_add_project.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 6px; /* Consistent padding */
                border-radius: 4px;
                font-size: 16px; /* Keep font size as is */
                color: #333333; /* Match default text color */
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: #dddddd;
            }
            QToolButton:pressed {
                background-color: #cccccc;
            }
        """)
        self.btn_add_project.clicked.connect(self.add_project_requested.emit)
        top_row_layout.addWidget(self.btn_add_project)
        top_row_layout.addStretch(1)  # Push buttons to the left

        main_layout.addLayout(top_row_layout)
        main_layout.addWidget(self.list_projects)

        self.list_projects.itemClicked.connect(self._on_project_clicked)
        self.project_store.changed.connect(self.refresh_project_list)
        self.refresh_project_list()

    def setup_initial_toggle_state(self):
        """
        Sets the initial visibility of list_projects and the toggle button's icon/tooltip
        based on the splitter's current sizes. Called by Workspace after splitter setup.
        """
        if not self._splitter or not self._splitter.sizes():  # Guard against premature calls
            return

        initial_width = self._splitter.sizes()[0]
        if initial_width <= self.COLLAPSED_WIDTH:
            self.list_projects.hide()
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self._btn_toggle.setToolTip("Expand sidebar")
            # If Workspace set a very small size, force it to COLLAPSED_WIDTH
            # and ensure the other pane's size is preserved.
            # This part of the logic might be redundant if Workspace always sets valid initial sizes.
            current_sizes = self._splitter.sizes()
            if len(current_sizes) > 1 and current_sizes[0] != self.COLLAPSED_WIDTH:
                self._splitter.setSizes([self.COLLAPSED_WIDTH, current_sizes[1]])
        else:
            self.list_projects.show()
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
            self._btn_toggle.setToolTip("Collapse sidebar")

    def _toggle(self):
        current_width = self._splitter.sizes()[0]
        current_sizes = self._splitter.sizes()  # Get all current sizes

        if not self.list_projects.isVisible() or current_width == self.COLLAPSED_WIDTH:
            # EXPAND
            expanded_width = self._splitter.property("last_expanded_width") or 220
            self.list_projects.show()
            if len(current_sizes) > 1:
                current_sizes[0] = expanded_width
            else:  # Should not happen with a 2-pane splitter
                current_sizes = [expanded_width, 0] 
            self._splitter.setSizes(current_sizes)
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))   # Collapse icon
            self._btn_toggle.setToolTip("Collapse sidebar")
        else:
            # COLLAPSE
            self._splitter.setProperty("last_expanded_width", current_width)
            self.list_projects.hide()
            if len(current_sizes) > 1:
                current_sizes[0] = self.COLLAPSED_WIDTH
            else:  # Should not happen
                current_sizes = [self.COLLAPSED_WIDTH, 0]
            self._splitter.setSizes(current_sizes)
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))  # Expand icon
            self._btn_toggle.setToolTip("Expand sidebar")
        self.toggled.emit()

    def _on_project_clicked(self, item: QListWidgetItem):
        project = item.data(Qt.UserRole) 
        if isinstance(project, CompareProject):  # Ensure it's the correct type
            self.project_selected.emit(project)

    def refresh_project_list(self):
        """Clears and repopulates the project list from the project store."""
        current_project_data = None
        if self.list_projects.currentItem():
            current_project_data = self.list_projects.currentItem().data(Qt.UserRole)

        self.list_projects.clear()
        new_current_item = None
        for proj in self.project_store.projects:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, proj)
            text_to_set = proj.name
            if proj.is_sample:
                prefix_tag = ""
                if proj.name == "強密碼合規範例":
                    prefix_tag = "<font color='#1565c0'>SAMPLE</font>&nbsp;"  # Blue tag
                elif proj.name == "風險清冊範例":
                    prefix_tag = "<font color='#2e7d32'>SAMPLE</font>&nbsp;"  # Green tag
                else:
                    prefix_tag = "<font color='gray'>SAMPLE</font>&nbsp;"  # Generic
                text_to_set = prefix_tag + proj.name
            item.setText(text_to_set)  # QListWidgetItem should render basic HTML for text
            item.setData(Qt.DisplayRole, proj.name)   # plain text for look-ups
            self.list_projects.addItem(item)

            # If using QLabel for rich text:
            # item = QListWidgetItem() # Create item without text
            # label = QLabel(display_text)
            # label.setTextFormat(Qt.RichText) # Ensure HTML is parsed
            # self.list_projects.addItem(item)
            # self.list_projects.setItemWidget(item, label) # Set QLabel as the widget for the item
            # item.setData(Qt.UserRole, proj) # Associate CompareProject object AFTER adding item

            if current_project_data == proj:
                new_current_item = item
        
        if new_current_item:
            self.list_projects.setCurrentItem(new_current_item)
        elif self.list_projects.count() > 0:
            self.list_projects.setCurrentRow(0)  # Select first item if previous selection is gone
            # Emit project_selected for the newly selected first item
            first_item_project = self.list_projects.item(0).data(Qt.UserRole)
            if isinstance(first_item_project, CompareProject):
                self.project_selected.emit(first_item_project)
        else:
            # If list is empty, emit a signal with None or handle as needed
            # For now, this implies no project is selected. Workspace handles this.
            pass
