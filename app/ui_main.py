from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtCore import Qt, QSettings, QThreadPool, QRunnable, QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QProgressDialog,
)

from .compare_manager import CompareManager
from .logger import logger
from .settings import Settings
from .settings_dialog import SettingsDialog

# ----------------------------------------------------------------------------
# Worker (unchanged in spirit)
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
# Project model & widgets
# ----------------------------------------------------------------------------
@dataclass
class CompareProject(QObject):
    changed = Signal()
    name: str
    input_path: Optional[Path] = None  # internal regulation (one)
    ref_paths: List[Path] = field(default_factory=list)  # external regulations
    results: dict[str, str] = field(default_factory=dict)  # ref_path -> markdown

    editor_idx: int = -1  # QStackedWidget index for ProjectEditor
    viewer_idx: int = -1  # index for ResultsViewer

    def __post_init__(self):
        super().__init__()

    @property
    def ready(self) -> bool:
        return self.input_path is not None and bool(self.ref_paths)

    @property
    def has_results(self) -> bool:
        return bool(self.results)

    def set_input(self, path: Path | None):
        self.input_path = path
        self.results.clear()
        self.changed.emit()

    def set_refs(self, paths: list[Path]):
        self.ref_paths = paths
        self.results.clear()
        self.changed.emit()

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for storage."""
        return {
            "name": self.name,
            "input_path": str(self.input_path) if self.input_path else None,
            "ref_paths": [str(p) for p in self.ref_paths],
            "results": self.results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareProject":
        """Create project from dictionary."""
        return cls(
            name=data["name"],
            input_path=Path(data["input_path"]) if data["input_path"] else None,
            ref_paths=[Path(p) for p in data["ref_paths"]],
            results=data["results"],
        )


class ProjectEditor(QWidget):
    """用於選擇檔案與啟動比較的介面"""

    compare_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self._build_ui()
        self.project.changed.connect(self._refresh)
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignTop)
        lay.setSpacing(20)
        lay.setContentsMargins(20, 20, 20, 20)

        # 專案標題和操作按鈕
        title_row = QHBoxLayout()
        title = QLabel(f"<h2>{self.project.name}</h2>")
        title.setStyleSheet("margin: 0;")
        title_row.addWidget(title)

        # 重命名按鈕
        btn_rename = QToolButton()
        btn_rename.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        btn_rename.setToolTip("重命名專案")
        btn_rename.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)
        btn_rename.clicked.connect(self._rename_project)
        title_row.addWidget(btn_rename)

        # 刪除按鈕
        btn_delete = QToolButton()
        btn_delete.setIcon(self.style().standardIcon(QStyle.SP_DialogDiscardButton))
        btn_delete.setToolTip("刪除專案")
        btn_delete.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #ffebee;
            }
        """)
        btn_delete.clicked.connect(self._delete_project)
        title_row.addWidget(btn_delete)

        title_row.addStretch()
        lay.addLayout(title_row)

        # 檔案上傳區域
        upload_frame = QWidget()
        upload_frame.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        upload_lay = QVBoxLayout(upload_frame)
        upload_lay.setSpacing(16)

        # 內規上傳
        input_group = QWidget()
        input_lay = QVBoxLayout(input_group)
        input_lay.setSpacing(8)
        
        input_label = QLabel("內規檔案")
        input_label.setStyleSheet("font-weight: bold;")
        input_lay.addWidget(input_label)
        
        input_btn = QPushButton("選擇內規 JSON")
        input_btn.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        input_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: white;
                border: 1px solid #e0e0e0;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        input_btn.clicked.connect(self._choose_input)
        input_lay.addWidget(input_btn)
        
        self.lbl_input = QLabel("<i>未選擇</i>")
        self.lbl_input.setStyleSheet("color: #666;")
        input_lay.addWidget(self.lbl_input)
        
        upload_lay.addWidget(input_group)

        # 外規上傳
        ref_group = QWidget()
        ref_lay = QVBoxLayout(ref_group)
        ref_lay.setSpacing(8)
        
        ref_label = QLabel("外規檔案")
        ref_label.setStyleSheet("font-weight: bold;")
        ref_lay.addWidget(ref_label)
        
        ref_btn = QPushButton("選擇外規 JSON")
        ref_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        ref_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: white;
                border: 1px solid #e0e0e0;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        ref_btn.clicked.connect(self._add_refs)
        ref_lay.addWidget(ref_btn)
        
        self.lbl_refs = QLabel("<i>未選擇</i>")
        self.lbl_refs.setStyleSheet("color: #666;")
        ref_lay.addWidget(self.lbl_refs)
        
        upload_lay.addWidget(ref_group)
        lay.addWidget(upload_frame)

        # 比較按鈕
        self.btn_compare = QPushButton("開始比較")
        self.btn_compare.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border-radius: 6px;
                background-color: #2196f3;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
            }
        """)
        self.btn_compare.clicked.connect(lambda: self.compare_requested.emit(self.project))
        lay.addWidget(self.btn_compare, alignment=Qt.AlignCenter)
        lay.addStretch()

    def _rename_project(self):
        name, ok = QInputDialog.getText(
            self,
            "重命名專案",
            "請輸入新的專案名稱：",
            text=self.project.name
        )
        if ok and name:
            parent = self.parent()
            if isinstance(parent, MainWindow):
                parent._update_project_name(self.project, name)

    def _delete_project(self):
        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除專案「{self.project.name}」嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            parent = self.parent()
            if isinstance(parent, MainWindow):
                parent._remove_project(self.project)

    # ------ File pickers ----------------------------------------------
    def _choose_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇內規 JSON", "", "JSON Files (*.json)")
        self.project.set_input(Path(path) if path else None)

    def _add_refs(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "選擇外規 JSON", "", "JSON Files (*.json)")
        if paths:
            self.project.set_refs([Path(p) for p in paths])

    # ------------------------------------------------------------------
    def _refresh(self):
        """更新 UI 顯示"""
        # 更新標題
        title = self.findChild(QLabel)
        if title:
            title.setText(f"<h2>{self.project.name}</h2>")
        
        # 更新檔案路徑顯示
        self.lbl_input.setText(str(self.project.input_path) if self.project.input_path else "<i>未選擇</i>")
        if self.project.ref_paths:
            self.lbl_refs.setText("\n".join(str(p) for p in self.project.ref_paths))
        else:
            self.lbl_refs.setText("<i>未選擇</i>")
        self.btn_compare.setEnabled(self.project.ready)


class ResultsViewer(QWidget):
    """顯示結果 (Markdown) – Tab 每個外規一頁"""

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # 標題和操作按鈕
        title_row = QHBoxLayout()
        title = QLabel(f"<h2>{self.project.name} - 比較結果</h2>")
        title.setStyleSheet("margin: 0;")
        title_row.addWidget(title)

        # 返回按鈕
        btn_back = QPushButton("返回編輯")
        btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        btn_back.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: white;
                border: 1px solid #e0e0e0;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        btn_back.clicked.connect(self._go_back)
        title_row.addWidget(btn_back)

        # 匯出按鈕
        btn_export = QPushButton("匯出結果")
        btn_export.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        btn_export.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: #2196f3;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        btn_export.clicked.connect(self._export_results)
        title_row.addWidget(btn_export)

        title_row.addStretch()
        lay.addLayout(title_row)

        # 結果標籤頁
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #e0e0e0;
            }
        """)

        for ref in self.project.ref_paths:
            md = self.project.results.get(str(ref), "(無結果)")
            view = QTextBrowser()
            view.setStyleSheet("""
                QTextBrowser {
                    border: none;
                    background-color: white;
                    padding: 16px;
                }
            """)
            view.setMarkdown(md)
            tabs.addTab(view, ref.stem)

        lay.addWidget(tabs)

    def _go_back(self):
        parent = self.parent()
        if isinstance(parent, MainWindow):
            parent.stack.setCurrentIndex(self.project.editor_idx)

    def _export_results(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出結果",
            "",
            "Markdown Files (*.md);;PDF Files (*.pdf)"
        )
        if path:
            path = Path(path)
            if path.suffix == ".pdf":
                # TODO: 實現 PDF 匯出
                QMessageBox.warning(self, "尚未實現", "PDF 匯出功能尚未實現")
            else:
                # 匯出 Markdown
                content = "\n\n---\n\n".join(
                    f"# {ref.stem}\n\n{md}"
                    for ref, md in self.project.results.items()
                )
                path.write_text(content, encoding="utf-8")
                QMessageBox.information(self, "成功", "結果已匯出")

    def _refresh(self):
        """更新 UI 顯示"""
        # 更新標題
        title = self.findChild(QLabel)
        if title:
            title.setText(f"<h2>{self.project.name} - 比較結果</h2>")
        
        # 更新標籤頁內容
        tabs = self.findChild(QTabWidget)
        if tabs:
            for i in range(tabs.count()):
                ref = self.project.ref_paths[i]
                md = self.project.results.get(str(ref), "(無結果)")
                view = tabs.widget(i)
                if isinstance(view, QTextBrowser):
                    view.setMarkdown(md)


# ----------------------------------------------------------------------------
# Main Window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, manager: CompareManager, settings: Settings):
        super().__init__()
        self.setWindowTitle("Regulens‑AI")
        self.manager = manager
        self.settings = settings
        self.threadpool = QThreadPool()

        self._projects: list[CompareProject] = []
        
        # 先建立 UI 元素
        self._build_menubar()
        self._build_body()
        
        # 然後再載入專案
        self._load_projects()

    def _load_projects(self):
        """從設定檔載入專案"""
        projects_data = self.settings.get("projects", [])
        for data in projects_data:
            try:
                proj = CompareProject.from_dict(data)
                self._projects.append(proj)
                # 創建編輯器和查看器
                editor = ProjectEditor(proj)
                editor.compare_requested.connect(self._run_compare)
                proj.editor_idx = self.stack.addWidget(editor)
                if proj.has_results:
                    viewer = ResultsViewer(proj)
                    proj.viewer_idx = self.stack.addWidget(viewer)
                # 添加到列表
                item = QListWidgetItem(proj.name)
                self.list_projects.addItem(item)
            except Exception as e:
                logger.error("Failed to load project: %s", str(e))
                # 顯示錯誤訊息給使用者
                QMessageBox.warning(
                    self,
                    "載入專案失敗",
                    f"無法載入專案：{str(e)}\n該專案將被跳過。"
                )

    def _save_projects(self):
        """保存專案到設定檔"""
        projects_data = [proj.to_dict() for proj in self._projects]
        self.settings.set("projects", projects_data)

    # ------------------------------------------------------------------
    # UI 合成
    # ------------------------------------------------------------------
    def _build_body(self):
        """Builds the *three* primary regions: sidebar, intro-page, workspace."""

        # ------------------------------------------------------------------
        # 1️⃣ Splitter – sidebar | main-stack
        # ------------------------------------------------------------------
        self.splitter = QSplitter(Qt.Horizontal, self)

        # ----- Sidebar --------------------------------------------------
        self.sidebar = QWidget()
        sb_lay = QVBoxLayout(self.sidebar)
        sb_lay.setContentsMargins(4, 4, 4, 4)
        sb_lay.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)

        # collapse button
        self.btn_toggle = QToolButton()
        self.btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.btn_toggle.setToolTip("折疊側邊欄")
        self.btn_toggle.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.btn_toggle.clicked.connect(self._toggle_sidebar)
        top_row.addWidget(self.btn_toggle)

        # add-project button
        self.btn_add = QToolButton()
        self.btn_add.setText("＋")
        self.btn_add.setToolTip("新增專案")
        self.btn_add.setStyleSheet("""
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
        self.btn_add.clicked.connect(self._add_project)
        top_row.addWidget(self.btn_add)

        top_row.addStretch(1)
        sb_lay.addLayout(top_row)

        # project list
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
                background-color: #e0e0e0;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
        """)
        self.list_projects.currentRowChanged.connect(self._show_project)
        sb_lay.addWidget(self.list_projects, 1)

        self.splitter.addWidget(self.sidebar)

        # ----- Main stack (intro page + project stack) ------------------
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(1, 1)

        # index 0 → introduction page
        self.intro_page = self._build_intro_page()
        self.stack.addWidget(self.intro_page)

        # restore sidebar width (or hidden)
        sett = QSettings("Regulens", "Regulens‑AI")
        if sett.value("sidebar_hidden", False, type=bool):
            self.sidebar.hide()
            self.btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self.btn_toggle.setToolTip("展開側邊欄")
        elif sett.contains("splitter"):
            self.splitter.restoreState(sett.value("splitter", type=bytes))
        else:
            self.splitter.setSizes([220, 680])

        self.setCentralWidget(self.splitter)

    # ------------------------------------------------------------------
    # Intro page
    # ------------------------------------------------------------------
    def _build_intro_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignCenter)

        title = QLabel("<h1>Regulens-AI</h1><p>快速、可靠地比較內外規</p>")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        # buttons row
        btn_row = QHBoxLayout()

        btn_start = QPushButton("Get Started")
        btn_start.setFixedHeight(38)
        btn_start.setStyleSheet("border-radius:19px; padding:0 24px;")
        btn_start.clicked.connect(lambda: self._add_project())
        btn_row.addWidget(btn_start)

        btn_settings = QPushButton("Settings")
        btn_settings.setFixedHeight(38)
        btn_settings.setStyleSheet("border-radius:19px; padding:0 24px;")
        btn_settings.clicked.connect(self._open_settings)
        btn_row.addWidget(btn_settings)

        lay.addLayout(btn_row)
        return page

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
        base = self.settings.get("base_url", "")
        key = self.settings.get("api_key", "")
        timeout = int(self.settings.get("timeout", 30))
        self.manager.api_client.base_url = base
        self.manager.api_client.api_key = key
        self.manager.api_client.timeout = timeout

    # ------------------------------------------------------------------
    # Sidebar logic
    # ------------------------------------------------------------------
    def _toggle_sidebar(self):
        """Completely hide/show the sidebar – only two states."""
        hidden = self.sidebar.isVisible()
        if hidden:
            self.sidebar.hide()
            self.btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            self.btn_toggle.setToolTip("展開側邊欄")
            self.settings.set("sidebar_hidden", True)
        else:
            self.sidebar.show()
            self.btn_toggle.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
            self.btn_toggle.setToolTip("折疊側邊欄")
            self.settings.set("sidebar_hidden", False)

    def _add_project(self):
        proj = CompareProject(name=f"Project {len(self._projects) + 1}")
        self._projects.append(proj)
        self._save_projects()  # 保存專案

        # editor widget first (保證 _show_project 能找到 index)
        editor = ProjectEditor(proj)
        editor.compare_requested.connect(self._run_compare)
        proj.editor_idx = self.stack.addWidget(editor)

        item = QListWidgetItem(proj.name)
        self.list_projects.addItem(item)
        self.list_projects.setCurrentItem(item)

        # auto-switch to project list if intro page is showing
        if self.stack.currentWidget() is self.intro_page:
            self.list_projects.setCurrentRow(self._projects.index(proj))

    def _show_project(self, row: int):
        if row < 0 or row >= len(self._projects):
            return
        proj = self._projects[row]
        # choose viewer or editor
        idx = proj.viewer_idx if proj.has_results else proj.editor_idx
        if idx != -1:
            self.stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Comparison flow
    # ------------------------------------------------------------------
    def _run_compare(self, proj: CompareProject):
        if not proj.ready:
            return
        prog = QProgressDialog("Comparing…", None, 0, len(proj.ref_paths), self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setCancelButton(None)
        prog.show()

        def task():
            for i, ref in enumerate(proj.ref_paths, start=1):
                resp = asyncio.run(self.manager.acompare(proj.input_path, ref))  # type: ignore[arg-type]
                proj.results[str(ref)] = resp.result
                prog.setValue(i)
            return proj

        worker = _Worker(task)
        worker.signals.error.connect(lambda e: self._compare_error(e, prog))
        worker.signals.finished.connect(lambda p: self._compare_done(p, prog))
        self.threadpool.start(worker)

    def _compare_error(self, err: Exception, dlg: QProgressDialog):
        dlg.close()
        QMessageBox.critical(self, "比較失敗", str(err))

    def _compare_done(self, proj: CompareProject, dlg: QProgressDialog):
        dlg.close()
        logger.info("comparison finished for %s", proj.name)
        # create viewer if first time
        if proj.viewer_idx == -1:
            viewer = ResultsViewer(proj)
            proj.viewer_idx = self.stack.addWidget(viewer)
        # show viewer
        self.stack.setCurrentIndex(proj.viewer_idx)
        self._save_projects()  # 保存專案

        # auto-switch to project list if intro page is showing
        if self.stack.currentWidget() is self.intro_page:
            self.list_projects.setCurrentRow(self._projects.index(proj))

    # ------------------------------------------------------------------
    # persist splitter state
    # ------------------------------------------------------------------
    def closeEvent(self, ev):  # noqa: D401
        st = self.splitter.saveState()
        QSettings("Regulens", "Regulens‑AI").setValue("splitter", st)
        super().closeEvent(ev)

    def _remove_project(self, proj: CompareProject):
        """移除專案及其相關的 UI 元素"""
        idx = self._projects.index(proj)
        
        # 移除相關的 widget
        if proj.editor_idx != -1:
            editor = self.stack.widget(proj.editor_idx)
            self.stack.removeWidget(editor)
            editor.deleteLater()
        if proj.viewer_idx != -1:
            viewer = self.stack.widget(proj.viewer_idx)
            self.stack.removeWidget(viewer)
            viewer.deleteLater()
        
        # 移除專案
        self._projects.pop(idx)
        self.list_projects.takeItem(idx)
        self._save_projects()  # 保存專案
        
        # 切換到其他專案或首頁
        if self._projects:
            self.list_projects.setCurrentRow(0)
        else:
            self.stack.setCurrentWidget(self.intro_page)
            
        # 更新所有專案的索引
        for i, p in enumerate(self._projects):
            if p.editor_idx > proj.editor_idx:
                p.editor_idx -= 1
            if p.viewer_idx > proj.viewer_idx:
                p.viewer_idx -= 1

    def _update_project_name(self, proj: CompareProject, new_name: str):
        """更新專案名稱"""
        proj.name = new_name
        idx = self._projects.index(proj)
        self.list_projects.item(idx).setText(new_name)
        self._save_projects()  # 保存專案
        
        # 更新編輯器和查看器的標題
        if proj.editor_idx != -1:
            editor = self.stack.widget(proj.editor_idx)
            if isinstance(editor, ProjectEditor):
                editor.project.name = new_name
                editor._refresh()
        if proj.viewer_idx != -1:
            viewer = self.stack.widget(proj.viewer_idx)
            if isinstance(viewer, ResultsViewer):
                viewer.project.name = new_name
                viewer._refresh()

    def resizeEvent(self, event):
        """處理視窗大小改變事件"""
        super().resizeEvent(event)


# ----------------------------------------------------------------------------
# Manual launch
# ----------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    from .api_client import ApiClient

    qapp = QApplication(sys.argv)
    sett = Settings()
    client = ApiClient(sett.get("base_url", "https://api.example.com"), sett.get("api_key", ""))
    mgr = CompareManager(client)

    win = MainWindow(mgr, sett)
    win.resize(1100, 720)
    win.show()
    sys.exit(qapp.exec())