from __future__ import annotations

import asyncio
import sys
# from pathlib import Path  # Keep for type hints if CompareProject uses it and is passed around
# from typing import List, Optional, Dict, Any # Keep if type hints for CompareProject use them

from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,  # For SettingsDialog
    QMainWindow,
    QMessageBox,  # For error reporting
    QProgressDialog,  # For comparison progress
)

# Local imports
from .logger import logger
from .settings import Settings
from .settings_dialog import SettingsDialog
from .models.project import CompareProject
from .pipeline import run_pipeline, PipelineSettings # Added
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
        self.settings = settings  # For SettingsDialog
        self.project_store = ProjectStore()  # Manages all project data
        self.threadpool = QThreadPool()

        self._build_menubar()

        self.intro_page = IntroPage()
        self.intro_page.start_requested.connect(self._enter_workspace)
        self.setCentralWidget(self.intro_page)
        
        self.workspace = None  # Will be initialized in _enter_workspace

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

    def _ensure_settings_configured(self) -> bool:
        required_fields = ["openai_api_key", "embedding_model", "llm_model"]
        missing_fields = [field for field in required_fields if not self.settings.get(field)]

        if missing_fields:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("組態設定不完整") # Configuration Incomplete
            msg_box.setText("請先設定 OpenAI API Key 與模型參數，才能執行比較") # Please set OpenAI API Key and model parameters to proceed.
            open_settings_button = msg_box.addButton("開啟設定", QMessageBox.ActionRole) # Open Settings
            cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole) # Cancel
            msg_box.setDefaultButton(open_settings_button)
            
            msg_box.exec()

            if msg_box.clickedButton() == cancel_button:
                return False
            elif msg_box.clickedButton() == open_settings_button:
                self._open_settings()
                # Re-check after settings dialog is closed
                still_missing = [field for field in required_fields if not self.settings.get(field)]
                if still_missing:
                    QMessageBox.warning(self, "組態設定不完整", "設定仍未完成，無法繼續執行。") # Settings still incomplete, cannot proceed.
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
    
        prog = QProgressDialog("正在處理專案...", "取消", 0, 0, self) # Indeterminate progress
        prog.setWindowModality(Qt.WindowModal)
        # prog.setCancelButton(None) # Allow cancellation if pipeline supports it
        prog.show()

        def task():
            try:
                logger.info(f"Starting pipeline for project: {proj.name}")
                current_pipeline_settings = PipelineSettings.from_settings(self.settings)
                run_pipeline(proj, current_pipeline_settings)
                # run_pipeline is expected to update proj.report_path
                logger.info(f"Pipeline finished for {proj.name}. Report: {proj.report_path}")
            except Exception as e:
                logger.error(f"Pipeline execution failed for {proj.name}: {e}", exc_info=True)
                # Re-raise to be caught by _Worker's error handling
                raise
            return proj # Return the project, now potentially with report_path updated

        worker = _Worker(task)
        worker.signals.error.connect(lambda e: self._compare_error(e, prog))  # type: ignore[attr-defined]
        worker.signals.finished.connect(lambda p: self._compare_done(p, prog))  # type: ignore[attr-defined]
        self.threadpool.start(worker)

    def _compare_error(self, err: Exception, dlg: QProgressDialog):
        dlg.close()
        QMessageBox.critical(self, "比較失敗", str(err))

    def _compare_done(self, proj: CompareProject, dlg: QProgressDialog):  # type: ignore[no-redef]
        dlg.close()
        logger.info("comparison finished for %s", proj.name)
        # Project results are updated in the worker task.
        # Now, notify the workspace to display the results.
        proj.changed.emit()  # Emit changed to trigger ProjectStore save and UI updates
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
