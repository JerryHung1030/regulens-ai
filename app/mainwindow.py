from __future__ import annotations

import sys
# from pathlib import Path  # Keep for type hints if CompareProject uses it and is passed around
# from typing import List, Optional, Dict, Any # Keep if type hints for CompareProject use them

from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal, Qt, QMetaObject, Q_ARG
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,  # For SettingsDialog
    QMainWindow,
    QMessageBox,  # For error reporting
    QProgressDialog,  # For comparison progress
)

# Local imports
from .compare_manager import CompareManager
from .logger import logger
from .settings import Settings
from .settings_dialog import SettingsDialog
from .models.project import CompareProject  # For type hinting and _run_compare
# from app.widgets.project_editor import ProjectEditor # No longer directly used by MainWindow
# from app.widgets.results_viewer import ResultsViewer  # Used in _compare_done (needs review)
from .widgets.intro_page import IntroPage
from .views.workspace import Workspace
from .stores.project_store import ProjectStore

# ----------------------------------------------------------------------------
# Worker (unchanged in spirit) - This can stay as it's a generic worker
# ----------------------------------------------------------------------------


class _Signals(QObject):
    finished = Signal(object)
    error = Signal(Exception)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)   # 確保 QObject 初始化


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

    def __init__(self, manager: CompareManager, settings: Settings):
        super().__init__()
        self.setWindowTitle("Regulens‑AI")
        self.manager = manager
        self.settings = settings  # For SettingsDialog and API client
        
        # 確保預設使用 mock mode
        if self.settings.get("use_mock_api") is None:
            self.settings.set("use_mock_api", True)
            self.settings.set("mock_path", "sample_data/mock_responses")
            
        self.project_store = ProjectStore()  # Manages all project data
        self.threadpool = QThreadPool()

        self._build_menubar()
        self._reload_api_client()

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
            self._reload_api_client()

    def _reload_api_client(self):
        if self.settings.get("use_mock_api", False):
            from app.mock_api_client import MockApiClient
            mock_dir = self.settings.get("mock_path", "sample_data/mock_responses")
            client = MockApiClient(mock_dir)
        else:
            from app.api_client import ApiClient
            client = ApiClient(
                self.settings.get("base_url", ""),
                self.settings.get("api_key", ""),
                timeout=int(self.settings.get("timeout", 30)),
            )
        self.manager.api_client = client

    def _ensure_settings_configured(self) -> bool:
        base_url = self.settings.get("base_url", "")
        api_key = self.settings.get("api_key", "")

        if self.settings.get("use_mock_api", False):
            # 如果使用 mock，就不用檢查 base_url/api_key
            return True

        if not base_url or not api_key:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Configuration Required")
            msg_box.setText("Essential settings like API Base URL and API Key are missing. Please configure them now to proceed.")
            open_settings_button = msg_box.addButton("Open Settings", QMessageBox.ActionRole)
            cancel_button = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(open_settings_button)
            
            msg_box.exec()

            if msg_box.clickedButton() == cancel_button:
                return False
            elif msg_box.clickedButton() == open_settings_button:
                self._open_settings()  # Open the settings dialog
                # Re-check after settings dialog is closed
                base_url = self.settings.get("base_url", "")
                api_key = self.settings.get("api_key", "")
                if not base_url or not api_key:
                    QMessageBox.warning(self, "Configuration Incomplete", "Settings are still missing. Comparison cannot proceed.")
                    return False
                return True  # Settings are now configured
        return True  # Settings were already configured

    # ------------------------------------------------------------------
    # Comparison flow
    # ------------------------------------------------------------------
    def _run_compare(self, proj: CompareProject):  # type: ignore[no-redef]
        if not proj.ready:
            return
        
        if not self._ensure_settings_configured():
            return  # Stop if settings are not configured
    
        # 讓 progressDialog 成為物件屬性，避免被 lambda capture
        self._prog = QProgressDialog("Comparing…", None, 0, len(proj.ref_paths), self)
        self._prog.setWindowModality(Qt.WindowModal)
        self._prog.setCancelButton(None)
        self._prog.show()

        def task():
            # Retrieve RAG settings
            scenario_params = {
                "role_desc": self.settings.get("rag_role_desc", ""),
                "reference_desc": self.settings.get("rag_reference_desc", ""),
                "input_desc": self.settings.get("rag_input_desc", ""),
                "direction": self.settings.get("rag_direction", "both"),
                "rag_k": self.settings.get("rag_rag_k", 5),
                "cof_threshold": self.settings.get("rag_cof_threshold", 0.5),
                "llm_name": self.settings.get("rag_llm_name", "openai")
            }
            for i, ref in enumerate(proj.ref_paths, start=1):
                # 使用同步的 compare 方法而不是非同步的 acompare
                resp = self.manager.compare(proj.name, proj.input_path, ref, **scenario_params)  # type: ignore[arg-type]
                proj.results[str(ref)] = resp.result
                QMetaObject.invokeMethod(
                    self._prog, "setValue", Qt.QueuedConnection, Q_ARG(int, i)
                )

            return proj

        worker = _Worker(task)
        worker.signals.error.connect(self._compare_error)      # 直接接函式
        worker.signals.finished.connect(self._compare_done)
        self.threadpool.start(worker)

    def _compare_error(self, err: Exception):
        if hasattr(self, "_prog"):
            self._prog.close()
        QMessageBox.critical(self, "比較失敗", str(err))

    def _compare_done(self, proj: CompareProject):
        if hasattr(self, "_prog"):
            self._prog.close()
        logger.info("comparison finished for %s", proj.name)
        
        # 有結果 → 通知 UI 更新
        proj.changed.emit()

        # 使用既有的 signal-flow，讓 Workspace 掌管跳畫面
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
if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    sett = Settings()

    # 先給一個佔位的 CompareManager，真正的 client 會在 MainWindow 內 _reload_api_client() 決定
    from app.api_client import ApiClient
    mgr = CompareManager(ApiClient("", ""))

    win = MainWindow(mgr, sett)
    win.resize(1100, 720)
    win.show()
    sys.exit(qapp.exec())
