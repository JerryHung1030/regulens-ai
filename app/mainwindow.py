from __future__ import annotations

import sys
from pathlib import Path # Added
# from typing import List, Optional, Dict, Any, Callable # For type hints

from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMessageBox,
    # QProgressDialog, # No longer used
)

# Local imports
from .widgets.progress_panel import ProgressPanel  # Added
from .logger import logger
from .settings import Settings
from .settings_dialog import SettingsDialog
from .models.project import CompareProject
from .pipeline import run_pipeline, PipelineSettings  # Added
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
    progress_updated = Signal(int, int, str, int)  # Added for thread-safe progress updates


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

    def __init__(self, settings: Settings):
        super().__init__()
        self.setWindowTitle("Regulens‑AI")
        self.settings = settings
        self.project_store = ProjectStore()
        self.threadpool = QThreadPool()
        self._cancelled = False  # Added
        self._progress_panel: ProgressPanel | None = None  # Added

        self._build_menubar()

        self.intro_page = IntroPage()
        self.intro_page.start_requested.connect(self._enter_workspace)
        self.setCentralWidget(self.intro_page)
        
        self.workspace = None  # Will be initialized in _enter_workspace
        self.apply_theme()

    def _enter_workspace(self):
        if not self.workspace:  # Create workspace only if it doesn't exist
            self.workspace = Workspace(self.project_store, self)
            self.comparison_finished.connect(self.workspace.show_project_results)
        self.setCentralWidget(self.workspace)

    # ------------------------------------------------------------------
    # Menubar + settings
    # ------------------------------------------------------------------
    def _build_menubar(self):
        mb = self.menuBar()
        m_file = mb.addMenu("&File")
        act_set = QAction("Settings…", self)
        act_set.setShortcut("Ctrl+,")
        act_set.triggered.connect(self._open_settings)
        m_file.addAction(act_set)
        m_file.addSeparator()
        m_file.addAction("E&xit", QApplication.instance().quit, shortcut="Ctrl+Q")

    def _open_settings(self):
        d = SettingsDialog(self.settings, self)
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
        qss = ""
        try:
            if theme_setting == 'dark':
                qss_path = Path(__file__).parent / ".." / "assets" / "dark_theme.qss"
                if qss_path.exists():
                    qss = qss_path.read_text()
                else:
                    logger.error(f"Dark theme file not found: {qss_path}")
            elif theme_setting == 'light':
                qss_path = Path(__file__).parent / ".." / "assets" / "light_theme.qss"
                if qss_path.exists():
                    qss = qss_path.read_text()
                else:
                    logger.error(f"Light theme file not found: {qss_path}")
            # If theme_setting is 'system', qss remains "" which clears custom styles.
            
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
                logger.info(f"Applied {theme_setting} theme.")
            else: # Should not happen in a running Qt app
                logger.error("QApplication instance not found when applying theme.")

        except Exception as e:
            logger.error(f"Error applying theme '{theme_setting}': {e}", exc_info=True)

    def _ensure_settings_configured(self) -> bool:
        required_fields = ["openai_api_key", "embedding_model", "llm_model"]
        missing_fields = [field for field in required_fields if not self.settings.get(field)]

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

        self._cancelled = False  # Reset cancellation flag for new run
        self._progress_panel = ProgressPanel(self)  # Using new ProgressPanel
        self._progress_panel.cancelled.connect(self._handle_pipeline_cancellation)
        self._progress_panel.show()

        def task_wrapper(worker_signals: _Signals):  # Renamed to avoid conflict, pass signals
            try:
                logger.info(f"Starting pipeline for project: {proj.name}")
                current_pipeline_settings = PipelineSettings.from_settings(self.settings)

                # Define the progress callback for run_pipeline
                def progress_handler(stage_idx: int, total_stages: int, message: str, percent_complete: int):
                    # This is called from the worker thread, emit signal for main thread update
                    worker_signals.progress_updated.emit(stage_idx, total_stages, message, percent_complete)

                run_pipeline(
                    proj,
                    current_pipeline_settings,
                    progress_callback=progress_handler,  # Pass the new handler
                    cancel_cb=self._is_pipeline_cancelled  # Pass cancellation check
                )
                logger.info(f"Pipeline finished for {proj.name}. Report: {proj.report_path}")
            except Exception as e:
                logger.error(f"Pipeline execution failed for {proj.name}: {e}", exc_info=True)
                raise  # Re-raise to be caught by _Worker's error handling
            return proj

        worker = _Worker(lambda: task_wrapper(worker.signals))  # Pass worker's signals to task_wrapper
        worker.signals.error.connect(self._compare_error)  # Pass self._progress_panel implicitly
        worker.signals.finished.connect(self._compare_done)  # Pass self._progress_panel implicitly
        worker.signals.progress_updated.connect(self._update_progress_panel_on_signal)  # Connect new signal
        self.threadpool.start(worker)

    def _update_progress_panel_on_signal(self, stage_idx: int, total_stages: int, message: str, percent: int):
        """Slot to update ProgressPanel from worker thread signal."""
        if self._progress_panel:
            self._progress_panel.update_progress(stage_idx, total_stages, message, percent)

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

    def _compare_done(self, proj: CompareProject):  # dlg parameter removed
        if self._progress_panel:
            try:
                self._progress_panel.cancelled.disconnect(self._handle_pipeline_cancellation)
            except RuntimeError:
                logger.debug("Error disconnecting ProgressPanel.cancelled in _compare_done, possibly already disconnected.")
            self._progress_panel.accept()  # Close the panel
            self._progress_panel = None
        self._cancelled = False  # Reset for the next run

        logger.info("comparison finished for %s", proj.name)
        proj.changed.emit()
        self.comparison_finished.emit(proj)

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
    win = MainWindow(sett)
    win.resize(1100, 720)
    win.show()
    sys.exit(qapp.exec())
