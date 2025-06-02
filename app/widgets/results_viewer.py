from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QStyle,
    QApplication,
)
from PySide6.QtCore import Signal, Qt

from app.models.project import CompareProject
from app.logger import logger


class ResultsViewer(QWidget):
    """顯示結果 (Markdown) – Tab 每個外規一頁"""
    edit_requested = Signal(CompareProject)  # New signal

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        logger.info(f"Initializing ResultsViewer for project: {project.name}")
        self.project = project
        self._build_ui()
        self.project.changed.connect(self._refresh)  # Connect to project's changed signal
        logger.debug("ResultsViewer initialization completed")

    def _render_md_for_proc(self, proc_id: str) -> str:
        logger.debug(f"Rendering markdown for procedure ID: {proc_id}")
        markdown_parts = []
        try:
            # Ensure thread-safe access to project results
            for pa in self.project.get_results(): 
                if pa.procedure_doc_id == proc_id:
                    # Assuming summary_analysis is the correct attribute holding markdown string
                    markdown_parts.append(pa.summary_analysis) 
            
            if not markdown_parts:
                logger.warning(f"No analysis found for procedure ID: {proc_id}")
                return f"No analysis found for procedure ID: {proc_id}"
            
            # Join multiple assessments for the same procedure ID with a separator
            result = "\n\n---\n\n".join(markdown_parts)
            logger.debug(f"Successfully rendered markdown for procedure ID: {proc_id}")
            return result
        except Exception as e:
            logger.error(f"Error rendering markdown for procedure ID {proc_id}: {str(e)}")
            return f"Error rendering content: {str(e)}"

    def _build_ui(self):
        logger.debug("Building UI for ResultsViewer")
        # Clear existing layout if any, to prevent duplicating widgets on refresh
        layout = self.layout()
        if layout:
            logger.debug("Clearing existing layout")
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # 標題和操作按鈕
        title_row = QHBoxLayout()
        self._title = QLabel(f"<h2>{self.project.name} - 比較結果</h2>")
        self._title.setStyleSheet("margin: 0;")
        title_row.addWidget(self._title)

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

        title_row.addStretch()
        lay.addLayout(title_row)

        # 結果標籤頁
        self.tabs = QTabWidget()  # Store tabs as instance variable for _refresh
        self.tabs.setStyleSheet("""
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

        # Initial population of tabs is done in _refresh, called after _build_ui
        lay.addWidget(self.tabs)
        logger.debug("UI building completed, calling initial refresh")
        self._refresh()  # Call _refresh to populate tabs initially

    def _go_back(self):
        logger.info("Back button clicked, emitting edit_requested signal")
        self.edit_requested.emit(self.project)

    def _refresh(self):
        logger.info("Starting UI refresh")
        try:
            # Light-weight UI update when the project emits `changed`.
            # 1) Title
            self._title.setText(f"<h2>{self.project.name} - 比較結果</h2>")

            # 2) Tabs – rebuild only if result set actually changed
            new_proc_ids = {pa.procedure_doc_id for pa in self.project.get_results()}
            logger.debug(f"Found {len(new_proc_ids)} procedure IDs in results")
            
            current_tab_texts = set()
            for i in range(self.tabs.count()):
                # Check if the widget is our placeholder label
                widget = self.tabs.widget(i)
                if isinstance(widget, QLabel) and widget.text() == "沒有可顯示的結果。請先執行比較。":
                    # This indicates a "no results" state, treat old_proc_ids as empty for comparison logic
                    pass  # old_proc_ids remains empty or whatever it was before this special tab
                else:
                    current_tab_texts.add(self.tabs.tabText(i))
            
            old_proc_ids = current_tab_texts
            logger.debug(f"Current tab count: {self.tabs.count()}, Old proc IDs: {old_proc_ids}")

            if new_proc_ids == old_proc_ids and self.tabs.count() > 0:
                # Additional check: if new_proc_ids is empty and tabs already show "no results", also return
                if not new_proc_ids and self.tabs.count() == 1:
                    widget = self.tabs.widget(0)
                    if isinstance(widget, QLabel) and widget.text() == "沒有可顯示的結果。請先執行比較。":
                        logger.debug("No results state unchanged, skipping refresh")
                        return
                elif new_proc_ids:  # only return if new_proc_ids is not empty and matches
                    logger.debug("Tab content unchanged, skipping refresh")
                    return

            logger.info("Rebuilding tabs")
            # First remove all tabs and their widgets
            while self.tabs.count() > 0:
                widget = self.tabs.widget(0)
                if widget:
                    logger.debug(f"Removing tab at index 0: {self.tabs.tabText(0)}")
                    self.tabs.removeTab(0)
                    widget.deleteLater()

            if not new_proc_ids:
                logger.info("No results to display, showing placeholder")
                no_results_label = QLabel("沒有可顯示的結果。請先執行比較。")
                no_results_label.setAlignment(Qt.AlignCenter)
                self.tabs.addTab(no_results_label, "-")  # Use a placeholder title for the tab itself
                return

            # Create new tabs
            logger.info(f"Creating {len(new_proc_ids)} new tabs")
            for pid in sorted(list(new_proc_ids)):
                try:
                    logger.debug(f"Creating tab for procedure ID: {pid}")
                    viewer = QTextBrowser()
                    markdown_content = self._render_md_for_proc(pid)
                    viewer.setMarkdown(markdown_content)
                    self.tabs.addTab(viewer, pid)
                    logger.debug(f"Successfully created tab for procedure ID: {pid}")
                except Exception as e:
                    logger.error(f"Error creating tab for procedure {pid}: {str(e)}")
                    continue

            logger.info("UI refresh completed successfully")
        except Exception as e:
            logger.error(f"Error during UI refresh: {str(e)}")
            raise
