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
        self._splitter = splitter # Renamed from self.splitter to self._splitter

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2) # Consistent spacing

        # Top row for buttons
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(2)

        # Toggle Button
        self._btn_toggle = QToolButton()
        self._btn_toggle.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self._btn_toggle.clicked.connect(self._toggle)
        top_row_layout.addWidget(self._btn_toggle)
        
        # Set initial icon and tooltip based on splitter state
        if self._splitter.sizes()[0] == 0:
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self._btn_toggle.setToolTip("Expand sidebar")
        else:
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
            self._btn_toggle.setToolTip("Collapse sidebar")


        # Add project button
        self.btn_add_project = QToolButton()
        self.btn_add_project.setText("＋") # More compact for a top bar
        self.btn_add_project.setToolTip("Create a new project")
        self.btn_add_project.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
                font-size: 16px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.btn_add_project.clicked.connect(self.add_project_requested.emit)
        top_row_layout.addWidget(self.btn_add_project)
        top_row_layout.addStretch(1) # Push buttons to the left

        main_layout.addLayout(top_row_layout)
        
        self.list_projects = QListWidget()
        self.list_projects.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0; /* Standard selection color */
            }
            QListWidget::item:hover {
                background-color: #f0f0f0; /* Standard hover color */
            }
        """)
        main_layout.addWidget(self.list_projects)

        self.list_projects.itemClicked.connect(self._on_project_clicked)
        self.project_store.changed.connect(self._refresh_project_list) # Renamed for clarity
        self._refresh_project_list()


    def _toggle(self):
        sizes = self._splitter.sizes()
        if sizes[0] == 0:  # Sidebar is collapsed
            last_width = self._splitter.property("last_width") or 220
            sizes[0] = last_width
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
            self._btn_toggle.setToolTip("Collapse sidebar")
        else:  # Sidebar is expanded
            self._splitter.setProperty("last_width", sizes[0])
            sizes[0] = 0
            self._btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self._btn_toggle.setToolTip("Expand sidebar")
        
        self._splitter.setSizes(sizes)
        self.toggled.emit()

    def _on_project_clicked(self, item: QListWidgetItem):
        project = item.data(Qt.UserRole) 
        if isinstance(project, CompareProject): # Ensure it's the correct type
            self.project_selected.emit(project)

    def _refresh_project_list(self):
        """Clears and repopulates the project list from the project store."""
        current_project_data = None
        if self.list_projects.currentItem():
            current_project_data = self.list_projects.currentItem().data(Qt.UserRole)

        self.list_projects.clear()
        new_current_item = None
        for proj in self.project_store.projects:
            item = QListWidgetItem(proj.name)
            item.setData(Qt.UserRole, proj) # Associate CompareProject object
            self.list_projects.addItem(item)
            if current_project_data == proj:
                new_current_item = item
        
        if new_current_item:
            self.list_projects.setCurrentItem(new_current_item)
        elif self.list_projects.count() > 0:
            self.list_projects.setCurrentRow(0) # Select first item if previous selection is gone
            # Emit project_selected for the newly selected first item
            first_item_project = self.list_projects.item(0).data(Qt.UserRole)
            if isinstance(first_item_project, CompareProject):
                self.project_selected.emit(first_item_project)
        else:
            # If list is empty, emit a signal with None or handle as needed
            # For now, this implies no project is selected. Workspace handles this.
            pass
