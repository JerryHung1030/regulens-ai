from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter, QStackedWidget, QLabel
from PySide6.QtCore import Qt, QSettings

from app.stores.project_store import ProjectStore
from app.widgets.sidebar import Sidebar
from app.models.project import CompareProject
from app.widgets.project_editor import ProjectEditor
from app.widgets.results_viewer import ResultsViewer
from app.logger import logger


class Workspace(QWidget):
    def __init__(self, project_store: ProjectStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_store = project_store
        self.main_window = parent  # To access MainWindow's _run_compare, etc.
        self._project_connections = {}  # 用於跟踪項目的信號連接

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Use full space

        self.splitter = QSplitter(Qt.Horizontal)
        
        self.sidebar = Sidebar(self.project_store, self.splitter)  # Pass splitter
        self.splitter.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)

        self.splitter.setStretchFactor(1, 1)  # Main content area (stack) should expand
        
        # Restore splitter state (similar to original MainWindow)
        sett = QSettings("Regulens", "Regulens‑AI")
        if sett.contains("workspace_splitter"):
            self.splitter.restoreState(sett.value("workspace_splitter", type=bytes))
        else:
            self.splitter.setSizes([220, 680])  # Default sizes

        layout.addWidget(self.splitter)
        self.setLayout(layout)

        self.project_store.changed.connect(self._refresh_project_views)
        self.sidebar.project_selected.connect(self._show_project_in_stack)
        self.sidebar.add_project_requested.connect(self._add_new_project)

        self.sidebar.setup_initial_toggle_state()  # Call after splitter is fully set up
        
        self._refresh_project_views()  # Initial population and view setup
        
        if not self.project_store.projects:
            self.show_default_message()
        elif self.sidebar.list_projects.count() > 0:
            # Select the first project by default if any exist
            self.sidebar.list_projects.setCurrentRow(0)
            first_project_name = self.sidebar.list_projects.item(0).text()
            first_project = self.project_store.get_project_by_name(first_project_name)
            if first_project:
                self._show_project_in_stack(first_project)

    def show_default_message(self):
        default_label = QLabel("Select a project from the sidebar or create a new one.")
        default_label.setAlignment(Qt.AlignCenter)
        # Ensure no old widgets linger if we are resetting the stack
        while self.stack.count() > 0:
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()
        self.stack.addWidget(default_label)
        self.stack.setCurrentWidget(default_label)

    def _add_new_project(self):
        new_project_name = f"Project {len(self.project_store.projects) + 1}"
        proj = CompareProject(name=new_project_name)
        self.project_store.add(proj)
        # The project_store.changed signal will trigger _refresh_project_views
        # which will update the sidebar and select the new project.
        # Find and select the new project in the list
        for i in range(self.sidebar.list_projects.count()):
            if self.sidebar.list_projects.item(i).text() == new_project_name:
                self.sidebar.list_projects.setCurrentRow(i)
                self._show_project_in_stack(proj)
                break

    def _clear_stack(self):
        """Removes all widgets from the stack and deletes them."""
        while self.stack.count() > 0:
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            if widget:  # Check if widget is not None
                widget.deleteLater()

    def _refresh_project_views(self):
        """
        Refreshes the sidebar's project list and ensures the stack
        is either showing the current project or a default message.
        """
        self.sidebar.refresh_project_list()  # This will update the QListWidget in Sidebar

        current_project_name_in_sidebar = None
        if self.sidebar.list_projects.currentItem():
            current_project_name_in_sidebar = self.sidebar.list_projects.currentItem().text()

        if not self.project_store.projects:
            self.show_default_message()
            return

        if current_project_name_in_sidebar:
            project_to_display = self.project_store.get_project_by_name(current_project_name_in_sidebar)
            if project_to_display:
                self._show_project_in_stack(project_to_display)
            else:
                # The currently selected project in sidebar might have been deleted
                self.sidebar.list_projects.setCurrentRow(0)  # Select first if available
                if self.sidebar.list_projects.count() > 0:
                    first_project_name = self.sidebar.list_projects.item(0).text()
                    first_project = self.project_store.get_project_by_name(first_project_name)
                    if first_project:
                        self._show_project_in_stack(first_project)
                else:  # Should not happen if project_store.projects is not empty
                    self.show_default_message()
        elif self.project_store.projects:  # Projects exist, but none selected in sidebar
            self.sidebar.list_projects.setCurrentRow(0)  # Select first project
            first_project_name = self.sidebar.list_projects.item(0).text()
            project = self.project_store.get_project_by_name(first_project_name)
            if project:
                self._show_project_in_stack(project)
        else:  # No projects and nothing selected
            self.show_default_message()

    def _connect_project_signals(self, project: CompareProject):
        """連接項目的所有信號"""
        project_id = id(project)  # 使用項目的內存地址作為唯一標識符
        if project_id not in self._project_connections:
            self._project_connections[project_id] = []
            
        # 保存所有連接的引用
        connections = []
        
        # 連接 updated 信號
        project.updated.connect(self.project_store._save)
        connections.append((project.updated, self.project_store._save))
        
        project.updated.connect(self.sidebar.refresh_project_list)
        connections.append((project.updated, self.sidebar.refresh_project_list))
        
        # -------- deleted 信號：使用命名函數 --------
        def delete_slot(p=project):
            return self._handle_project_deleted(p)
            
        project.deleted.connect(delete_slot)
        connections.append((project.deleted, delete_slot))
        
        self._project_connections[project_id] = connections

    def _disconnect_project_signals(self, project: CompareProject):
        """斷開項目的所有信號連接"""
        project_id = id(project)
        if project_id in self._project_connections:
            for signal, slot in self._project_connections[project_id]:
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            del self._project_connections[project_id]

    def _show_project_in_stack(self, project: CompareProject | None):
        if project is None:
            self.show_default_message()
            return

        self._clear_stack()

        if project.has_results:
            viewer = ResultsViewer(project)
            viewer.edit_requested.connect(self._switch_to_editor)
            self.stack.addWidget(viewer)
            self.stack.setCurrentWidget(viewer)
            project.viewer_idx = self.stack.indexOf(viewer)
        else:
            editor = ProjectEditor(project)
            if self.main_window and hasattr(self.main_window, "_run_compare"):
                editor.compare_requested.connect(self.main_window._run_compare)
            
            # 連接項目的信號
            self._connect_project_signals(project)

            self.stack.addWidget(editor)
            self.stack.setCurrentWidget(editor)
            project.editor_idx = self.stack.indexOf(editor)

    def _show_project_editor(self, project: CompareProject):
        # This is a helper if navigating back from ResultsViewer to ProjectEditor
        self._clear_stack()
        editor = ProjectEditor(project)
        if self.main_window and hasattr(self.main_window, "_run_compare"):
            editor.compare_requested.connect(self.main_window._run_compare)
        project.updated.connect(self.project_store._save)  # Save when project details change
        # Ensure project.deleted is connected to ProjectStore.remove
        # This might be better done once when the project is first added to the store or when editor is first created
        # To avoid multiple connections if _show_project_editor is called multiple times for the same project.
        # However, QObject's signal/slot mechanism should handle duplicate connections gracefully (only connects once).
        self._disconnect_project_signals(project)
        self._connect_project_signals(project)

        self.stack.addWidget(editor)
        self.stack.setCurrentWidget(editor)
        project.editor_idx = self.stack.indexOf(editor)
        project.viewer_idx = -1  # Clear viewer index as we are back to editor

    def _switch_to_editor(self, project: CompareProject):
        """Switches the view to the ProjectEditor for the given project."""
        # This method is connected to ResultsViewer.edit_requested
        self._clear_stack()  # Clear current widget (ResultsViewer)
        
        # Create and show the editor for this project
        editor = ProjectEditor(project)
        if self.main_window and hasattr(self.main_window, "_run_compare"):
            editor.compare_requested.connect(self.main_window._run_compare)
        
        # Re-establish connections for project signals as they might have been specific to editor context
        # or if project instance is re-used/re-fetched.
        # These connections are crucial for reacting to model changes.
        try:
            project.updated.disconnect(self.project_store._save)
        except RuntimeError:
            pass
        project.updated.connect(self.project_store._save)
        
        try:
            # project.deleted.disconnect(self.project_store.remove)  # Old direct connection
            project.deleted.disconnect(self._handle_project_deleted)  # Disconnect previous if any
        except RuntimeError:
            pass
        project.deleted.connect(self._handle_project_deleted)  # New connection

        self.stack.addWidget(editor)
        self.stack.setCurrentWidget(editor)
        project.editor_idx = self.stack.indexOf(editor)
        project.viewer_idx = -1  # Ensure viewer_idx is reset

    def show_project_results(self, project: CompareProject):
        """
        Called when a comparison for a project is finished.
        Switches the view to the ResultsViewer for the given project.
        """
        if project is None or not project.has_results:
            logger.warning("show_project_results called with no project or no results.")
            return

        logger.info(f"Displaying results for project: {project.name}")
        self._clear_stack()  # Clear current widget (likely ProjectEditor)

        viewer = ResultsViewer(project)
        viewer.edit_requested.connect(self._switch_to_editor)
        
        self.stack.addWidget(viewer)
        self.stack.setCurrentWidget(viewer)
        project.viewer_idx = self.stack.indexOf(viewer)
        # project.editor_idx = -1 # Keep editor_idx, it's where 'back' goes

        # Ensure the sidebar selection reflects the currently viewed project
        # This might already be handled if the project was selected before comparison.
        # If not, find and select it.
        for i in range(self.sidebar.list_projects.count()):
            item = self.sidebar.list_projects.item(i)
            if item.data(Qt.UserRole) == project:
                self.sidebar.list_projects.setCurrentItem(item)
                break
        
        # Project results are part of project object, which should be saved by ProjectStore
        # if CompareProject.changed signal was emitted after results were added.
        # If not, explicitly save here or ensure CompareProject emits 'changed' or 'updated'.
        self.project_store._save()  # Explicitly save after results are added.

    def _handle_project_deleted(self, project_to_delete: CompareProject):
        logger.info(f"Handling deletion of project: {project_to_delete.name}")

        # 1. 先從 store 中移除項目
        logger.debug(f"Requesting removal of project {project_to_delete.name} from store.")
        self.project_store.remove(project_to_delete)

        # 2. 清理相關的 widget
        widgets_to_remove = []
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            if hasattr(widget, 'project') and widget.project == project_to_delete:
                widgets_to_remove.append(widget)
        
        for widget in widgets_to_remove:
            logger.debug(f"Removing widget {widget} for project {project_to_delete.name} from stack.")
            self.stack.removeWidget(widget)
            widget.deleteLater()

        # 3. 更新側邊欄
        self.sidebar.refresh_project_list()

        # 4. 更新顯示
        if not self.project_store.projects:
            self.show_default_message()
        else:
            # 選擇第一個可用的項目
            if self.sidebar.list_projects.count() > 0:
                self.sidebar.list_projects.setCurrentRow(0)
                first_project_name = self.sidebar.list_projects.item(0).text()
                first_project = self.project_store.get_project_by_name(first_project_name)
                if first_project:
                    self._show_project_in_stack(first_project)

        # 5. 斷開項目的所有信號連接
        self._disconnect_project_signals(project_to_delete)

    def closeEvent(self, event):
        """Save splitter state when the workspace (or main window) is closed."""
        sett = QSettings("Regulens", "Regulens‑AI")
        sett.setValue("workspace_splitter", self.splitter.saveState())
        super().closeEvent(event)
