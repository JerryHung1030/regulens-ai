from __future__ import annotations

import sys
from pathlib import Path # Added
# from typing import List, Optional, Dict, Any, Callable # For type hints

from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMessageBox,
    # QProgressDialog, # No longer used
)

# Local imports
from .widgets.progress_panel import ProgressPanel
from .logger import logger
from .settings import Settings
from .translator import Translator
from .settings_dialog import SettingsDialog
from .models.project import CompareProject
from .pipeline import run_pipeline # PipelineSettings is now instantiated within run_pipeline or its callees
# Import for _compare_done to load ProjectRunData
from .pipeline.pipeline_v1_1 import _load_run_json, ProjectRunData
# from app.widgets.project_editor import ProjectEditor
# from app.widgets.results_viewer import ResultsViewer
from .widgets.intro_page import IntroPage
from .views.workspace import Workspace
from .stores.project_store import ProjectStore

# ----------------------------------------------------------------------------
# Worker (unchanged in spirit) - This can stay as it's a generic worker
# ----------------------------------------------------------------------------


class _Signals(QObject):
    finished = Signal(object)
    error = Signal(Exception)
    progress_updated = Signal(float, str) # Signature changed: progress_float (0.0-1.0), message_str


class _Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _Signals()

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(res)
        except Exception as e:  # pragma: no cover
            self.signals.error.emit(e)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# Main Window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    comparison_finished = Signal(CompareProject)  # Signal to notify Workspace

    def __init__(self, settings: Settings, translator: Translator):
        super().__init__()
        # Title will be set by _retranslate_ui
        self.settings = settings
        self.translator = translator
        self.project_store = ProjectStore()
        self.threadpool = QThreadPool()
        self._cancelled = False  # Added
        self._progress_panel: ProgressPanel | None = None  # Added

        self._build_menubar()

        self.intro_page = IntroPage(self.translator) # Pass translator
        self.intro_page.start_requested.connect(self._enter_workspace)
        self.setCentralWidget(self.intro_page)
        
        self.workspace = None  # Will be initialized in _enter_workspace
        self.apply_theme() # Apply theme before showing
        
        # Connect translator signal and set initial translation
        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui()

    def _retranslate_ui(self):
        # This method will be expanded in later steps to update menus, etc.
        self.setWindowTitle(self.translator.get("main_window_title", "Regulens-AI"))

        if hasattr(self, 'file_menu') and hasattr(self, 'file_menu_title_key'):
            self.file_menu.setTitle(self.translator.get(self.file_menu_title_key, "&File"))
        if hasattr(self, 'settings_action') and hasattr(self, 'settings_action_text_key'):
            self.settings_action.setText(self.translator.get(self.settings_action_text_key, "Settings…"))
        if hasattr(self, 'exit_action') and hasattr(self, 'exit_action_text_key'):
            self.exit_action.setText(self.translator.get(self.exit_action_text_key, "E&xit"))
        
        logger.debug("MainWindow UI retranslated (title and menu)")

    def _enter_workspace(self):
        if not self.workspace:  # Create workspace only if it doesn't exist
            self.workspace = Workspace(self.project_store, self)
            self.comparison_finished.connect(self.workspace.show_project_results)
        self.setCentralWidget(self.workspace)

    # ------------------------------------------------------------------
    # Menubar + settings
    # ------------------------------------------------------------------
    def _build_menubar(self):
        menu_bar = self.menuBar()

        # File Menu
        self.file_menu_title_key = "main_menu_file"
        self.file_menu = menu_bar.addMenu(self.translator.get(self.file_menu_title_key, "&File"))

        # Settings Action
        self.settings_action_text_key = "main_action_settings"
        self.settings_action = QAction(self.translator.get(self.settings_action_text_key, "Settings…"), self)
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.triggered.connect(self._open_settings)
        self.file_menu.addAction(self.settings_action)

        self.file_menu.addSeparator()

        # Exit Action
        self.exit_action_text_key = "main_action_exit"
        self.exit_action = QAction(self.translator.get(self.exit_action_text_key, "E&xit"), self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(QApplication.instance().quit)
        self.file_menu.addAction(self.exit_action)

    def _open_settings(self):
        d = SettingsDialog(self.settings, self.translator, self)
        d.settings_saved.connect(self.apply_theme)
        if d.exec() == QDialog.accepted:
            self._reload_pipeline_settings()
            logger.info("Settings dialog accepted and pipeline settings reloaded.")

    def _reload_pipeline_settings(self):
        # This method will be updated when the new pipeline integration is clear.
        # For now, it can log the relevant settings or re-initialize a conceptual PipelineSettings object.
        logger.info("Reloading pipeline settings...")
        # Example:
        # pipeline_settings = {
        #     "openai_api_key": self.settings.get("openai_api_key"),
        #     "embedding_model": self.settings.get("embedding_model"),
        #     "llm_model": self.settings.get("llm_model"),
        # }
        # logger.info(f"Pipeline settings: {pipeline_settings}")
        # If there was a global or instance variable for pipeline config, update it here.
        pass

    def apply_theme(self):
        theme_setting = self.settings.get('theme', 'system') # Default to 'system'
        try:
            if theme_setting == 'system':
                # 檢測系統主題
                app = QApplication.instance()
                if app:
                    # 檢查系統是否處於深色模式
                    is_dark_mode = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
                    effective_theme = "dark" if is_dark_mode else "light"
                else:
                    effective_theme = "light"  # 默認使用淺色主題
            else:
                effective_theme = theme_setting.lower()

            from .utils.theme_manager import load_qss_with_theme
            qss = load_qss_with_theme(effective_theme)
            
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
                logger.debug(f"Applied {effective_theme} theme.")
            else: # Should not happen in a running Qt app
                logger.error("QApplication instance not found when applying theme.")

        except Exception as e:
            logger.error(f"Error applying theme '{theme_setting}': {e}", exc_info=True)

    def _ensure_settings_configured(self) -> bool:
        required_fields = [
            "openai.api_key", # Changed from "openai_api_key"
            "embedding_model",
            # New specific model settings:
            "llm.model_need_check",
            "llm.model_audit_plan",
            "llm.model_judge",
            # audit.retrieval_top_k is not listed as it has a default in PipelineSettings.
        ]
        # The check for "llm_model" as a fallback is removed as it's deprecated.
        # The specific models llm.model_need_check, llm.model_audit_plan, llm.model_judge
        # are now the primary ones to check.

        missing_fields = [field for field in required_fields if not self.settings.get(field)]
        
        # Check if the primary key 'openai.api_key' is missing or empty string
        # The previous list comprehension for missing_fields already covers this.
        # For example, if settings.get("openai.api_key") returns None or "", it's in missing_fields.

        if missing_fields:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("組態設定不完整")  # Configuration Incomplete
            msg_box.setText("請先設定 OpenAI API Key 與模型參數，才能執行比較")  # Please set OpenAI API Key and model parameters to proceed.
            open_settings_button = msg_box.addButton("開啟設定", QMessageBox.ActionRole)  # Open Settings
            cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole)  # Cancel
            msg_box.setDefaultButton(open_settings_button)
            
            msg_box.exec()

            if msg_box.clickedButton() == cancel_button:
                return False
            elif msg_box.clickedButton() == open_settings_button:
                self._open_settings()
                # Re-check after settings dialog is closed
                still_missing = [field for field in required_fields if not self.settings.get(field)]
                if still_missing:
                    QMessageBox.warning(self, "組態設定不完整", "設定仍未完成，無法繼續執行。")  # Settings still incomplete, cannot proceed.
                    return False
                return True
        return True

    # ------------------------------------------------------------------
    # Comparison flow
    # ------------------------------------------------------------------
    def _run_compare(self, proj: CompareProject):
        # The `proj.ready` check is now more comprehensive.
        if not proj.ready:
            QMessageBox.warning(self, "專案未就緒", "請確認所有必要的資料夾都已設定且包含有效的 .txt 檔案。")
            return
        
        if not self._ensure_settings_configured():
            # Message to user is handled within _ensure_settings_configured
            return

        self.apply_theme()

        self._cancelled = False  # Reset cancellation flag for new run
        self._progress_panel = ProgressPanel(self)  # Using new ProgressPanel
        self._progress_panel.cancelled.connect(self._handle_pipeline_cancellation)
        self._progress_panel.show()

        def task_wrapper(worker_signals: _Signals):
            try:
                logger.info(f"Starting pipeline for project: {proj.name}")
                # PipelineSettings instance is now created inside run_pipeline from self.settings

                # Define the progress callback for run_pipeline (float, str)
                def progress_handler(progress_float: float, message_str: str):
                    worker_signals.progress_updated.emit(progress_float, message_str)

                run_pipeline( # run_pipeline now expects the global self.settings
                    proj,
                    self.settings,
                    progress_callback=progress_handler,
                    cancel_cb=self._is_pipeline_cancelled
                )
                # For v1.1, primary output is run.json, not a single report_path from the pipeline function.
                logger.info(f"Pipeline task finished for {proj.name}. Results are in {proj.run_json_path}")
            except Exception as e:
                logger.error(f"Pipeline execution failed for {proj.name}: {e}", exc_info=True)
                raise
            return proj

        worker = _Worker(lambda: task_wrapper(worker.signals))
        worker.signals.error.connect(self._compare_error)
        worker.signals.finished.connect(self._compare_done)
        worker.signals.progress_updated.connect(self._update_progress_panel_on_signal)
        self.threadpool.start(worker)

    def _update_progress_panel_on_signal(self, progress_float: float, message: str): # Signature updated
        """Slot to update ProgressPanel from worker thread signal."""
        if self._progress_panel:
            self._progress_panel.update_progress(progress_float, message) # Pass new signature

    def _is_pipeline_cancelled(self) -> bool:
        """Used by run_pipeline to check for cancellation."""
        return self._cancelled

    def _handle_pipeline_cancellation(self):
        """Slot for ProgressPanel's cancelled signal."""
        logger.info("Pipeline cancellation requested by user via ProgressPanel.")
        self._cancelled = True
        # ProgressPanel handles its own closure via reject() when cancel button is clicked.
        # If pipeline aborts due to self._cancelled, _compare_error will be called.

    def _compare_error(self, err: Exception):  # dlg parameter removed
        if self._progress_panel:
            try:
                # Disconnect from panel's cancelled signal to avoid issues during cleanup
                self._progress_panel.cancelled.disconnect(self._handle_pipeline_cancellation)
            except RuntimeError:  # Signal might have already been disconnected or was never connected
                logger.debug("Error disconnecting ProgressPanel.cancelled, possibly already disconnected.")
            self._progress_panel.accept()  # Close the panel
            self._progress_panel = None
        self._cancelled = False  # Reset for the next run
        
        # Show error message
        # Check if error is due to cancellation to show a more specific message
        if "Cancelled by user" in str(err) or (isinstance(err, RuntimeError) and "cancel" in str(err).lower()):
            QMessageBox.information(self, "操作已取消", "流程已被使用者取消。")  # Operation Cancelled, The process was cancelled by the user.
        else:
            QMessageBox.critical(self, "比較失敗", str(err))  # Comparison Failed

    def _compare_done(self, proj: CompareProject):
        if self._progress_panel:
            try:
                self._progress_panel.cancelled.disconnect(self._handle_pipeline_cancellation)
            except RuntimeError:
                logger.debug("Error disconnecting ProgressPanel.cancelled in _compare_done, possibly already disconnected.")
            self._progress_panel.accept()
            self._progress_panel = None
        self._cancelled = False

        logger.info("Pipeline UI interaction finished for project %s", proj.name)

        # Load results from run.json into project.project_run_data
        if proj.run_json_path and proj.run_json_path.exists():
            logger.info(f"Loading results from {proj.run_json_path} into project.project_run_data for UI display.")
            try:
                # _load_run_json is imported from app.pipeline.pipeline_v1_1
                loaded_run_data = _load_run_json(proj.run_json_path)
                if loaded_run_data:
                    proj.project_run_data = loaded_run_data
                    logger.info(f"Successfully loaded run.json into project_run_data for {proj.name}")
                else:
                    # _load_run_json logs errors, but we can add a specific message here too
                    logger.error(f"Failed to parse run.json for {proj.name}, project_run_data will be empty or stale.")
                    proj.project_run_data = ProjectRunData(project_name=proj.name, control_clauses=[]) # Ensure it's not None
                    QMessageBox.warning(self, "Result Loading Error",
                                        f"Could not load or parse results from {proj.run_json_path}. Display may be empty or outdated.")
            except Exception as e: # Catch any other unexpected error during load
                logger.error(f"Unexpected error loading run.json for project {proj.name}: {e}", exc_info=True)
                proj.project_run_data = ProjectRunData(project_name=proj.name, control_clauses=[])
                QMessageBox.critical(self, "Result Loading Error",
                                     f"An unexpected error occurred while loading results: {e}")
        else:
            logger.warning(f"No run.json path found for project {proj.name} at {proj.run_json_path}, or file does not exist. Cannot load results into UI.")
            proj.project_run_data = ProjectRunData(project_name=proj.name, control_clauses=[]) # Ensure it's not None and empty
            QMessageBox.warning(self, "Result File Missing",
                                f"Result file (run.json) not found for project {proj.name}. Display may be empty.")

        proj.changed.emit() # Notify that project data (potentially project_run_data) has changed
        self.comparison_finished.emit(proj) # Notify workspace to update its view

    # ------------------------------------------------------------------
    # closeEvent is removed as Workspace handles its own splitter state.
    # QMainWindow's default closeEvent is sufficient.

    def resizeEvent(self, event):
        """處理視窗大小改變事件"""
        super().resizeEvent(event)


# ----------------------------------------------------------------------------
# Manual launch
# ----------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    qapp = QApplication(sys.argv)
    sett = Settings()
    # ApiClient and CompareManager are removed.
    # The MainWindow initialization is simplified.
    initial_lang = sett.get("language", "en")
    translator = Translator(initial_language=initial_lang)

    win = MainWindow(sett, translator)
    win.resize(1100, 720)
    win.show()
    sys.exit(qapp.exec())
