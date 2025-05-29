from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt # Assuming Qt might be needed for some features not explicitly listed but common in widgets
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QFileDialog,
    QMessageBox,
    QStyle,
)
from PySide6.QtCore import Signal # Added Signal import

from app.models.project import CompareProject


class ResultsViewer(QWidget):
    """顯示結果 (Markdown) – Tab 每個外規一頁"""
    edit_requested = Signal(CompareProject) # New signal

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
        self.edit_requested.emit(self.project)


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
        if title: # Check if title exists to prevent errors during initial build or if UI changes
            title.setText(f"<h2>{self.project.name} - 比較結果</h2>")
        
        # 更新標籤頁內容
        tabs = self.findChild(QTabWidget)
        if tabs: # Check if tabs exists
            for i in range(tabs.count()):
                # Ensure index is within bounds of ref_paths
                if i < len(self.project.ref_paths):
                    ref = self.project.ref_paths[i]
                    md = self.project.results.get(str(ref), "(無結果)")
                    view = tabs.widget(i)
                    if isinstance(view, QTextBrowser):
                        view.setMarkdown(md)
                else: # Handle case where tab count might mismatch ref_paths (e.g. during dynamic updates)
                    # Optionally log a warning or handle error
                    pass
