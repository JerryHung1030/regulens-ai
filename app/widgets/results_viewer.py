from __future__ import annotations

import re  # Added for ID shortening
import shutil  # Added for report export
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
    QFileDialog,  # Added for report export
    QMessageBox  # Added for report export feedback
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
            
            # Shorten IDs in the rendered markdown
            # Replaces: prefix_longhexstring -> prefix_1234...
            # (where 1234 are the first 4 chars of the hex string)
            try:
                result = re.sub(r'(norm_|procedure_|control_|evidence_|embed_set_|raw_doc_|chunk_text_|doc_)([0-9a-fA-F]{4})[0-9a-fA-F]{4,}', 
                                r'\1\2...', 
                                result)
                logger.debug(f"Successfully shortened IDs in markdown for procedure ID: {proc_id}")
            except Exception as re_e:
                logger.error(f"Error during ID shortening for procedure ID {proc_id}: {str(re_e)}")
                # Continue with unshortened result if regex fails for some reason
            
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
        title_row.addStretch(1)  # Add stretch before buttons to push them to the right

        # Export Report Button
        btn_export = QPushButton("匯出報告…")  # "Export Report..."
        btn_export.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        btn_export.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: #e0e0e0; /* Slightly different from back for distinction */
                border: 1px solid #cccccc;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        btn_export.clicked.connect(self._export_report)
        title_row.addWidget(btn_export)

        # 返回按鈕 (Back Button)
        btn_back = QPushButton("返回編輯")  # "Back to Edit"
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

        # title_row.addStretch() # Removed stretch from here
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
            if self.project:  # Check if project exists, useful if project could be None
                self._title.setText(f"<h2>{self.project.name} - 比較結果</h2>")
            else:
                self._title.setText("<h2>比較結果</h2>")  # Default title

            # 2) Tabs – rebuild only if result set actually changed
            new_proc_ids = set()
            if self.project:
                new_proc_ids = {pa.procedure_doc_id for pa in self.project.get_results()}
            logger.debug(f"Found {len(new_proc_ids)} procedure IDs in results")
            
            # Conditional refresh logic removed to ensure titles are always updated.
            # current_tab_texts = set()
            # for i in range(self.tabs.count()):
            #     # ... (widget check) ...
            #     else:
            #         current_tab_texts.add(self.tabs.tabText(i))
            
            # old_proc_ids = current_tab_texts # old_proc_ids is a misnomer here
            # logger.debug(f"Current tab count: {self.tabs.count()}, Old proc IDs: {old_proc_ids}")

            # if new_proc_ids == old_proc_ids and self.tabs.count() > 0: # This comparison is problematic
            #     # ... (conditional return)
            #     logger.debug("Tab content unchanged, skipping refresh")
            #     return

            logger.info("Rebuilding tabs")  # This will now always run if _refresh is called.
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
            logger.info(f"Creating {len(new_proc_ids)} new tabs")  # Keep this log
            tab_counter = 1  # Initialize tab counter for fallback names
            for pid in sorted(list(new_proc_ids)):  # Ensure sorted_pids is used (it's sorted list of new_proc_ids)
                try:
                    logger.debug(f"Creating tab for procedure ID: {pid}")  # Keep
                    viewer = QTextBrowser()
                    # Add setOpenExternalLinks(True) here as per plan item 5
                    viewer.setOpenExternalLinks(True) 
                    
                    markdown_content = self._render_md_for_proc(pid)
                    viewer.setMarkdown(markdown_content)  # Markdown content first

                    # New title generation logic
                    tab_title = pid  # Default title
                    # Ensure self.project exists and has the method
                    if hasattr(self.project, 'get_norm_doc_info') and callable(self.project.get_norm_doc_info):
                        doc_info = self.project.get_norm_doc_info(pid)
                        if doc_info:  # Check if info was found
                            original_filename = doc_info.get("original_filename")
                            raw_doc_id_val = doc_info.get("raw_doc_id")
                            if original_filename:
                                tab_title = original_filename
                            elif raw_doc_id_val:  # Use raw_doc_id if original_filename is not available
                                tab_title = raw_doc_id_val
                            else:  # Fallback if specific info is missing
                                tab_title = f"Procedure-{tab_counter}"
                                tab_counter += 1
                        else:  # Fallback if doc_info is empty or None (doc_id not found)
                            tab_title = f"Procedure-{tab_counter}"
                            tab_counter += 1
                    else:  # Fallback if project doesn't have the method (should not happen with step 1)
                        tab_title = f"Procedure-{tab_counter}"
                        tab_counter += 1
                    
                    self.tabs.addTab(viewer, tab_title)
                    logger.debug(f"Successfully created tab for procedure ID: {pid} with title {tab_title}")  # Update log
                except Exception as e:
                    logger.error(f"Error creating tab for procedure {pid}: {str(e)}")  # Keep
                    continue

            logger.info("UI refresh completed successfully")
        except Exception as e:
            logger.error(f"Error during UI refresh: {str(e)}")
            # Consider not raising here to prevent app crash if refresh fails,
            # but log it thoroughly. For now, keep raise to see errors during dev.
            raise

    def _export_report(self):
        if not self.project or not self.project.report_path:
            QMessageBox.warning(self, "沒有報告", "此專案的報告無法使用或尚未產生。")
            # Original English: "No Report", "The report for this project is not available or has not been generated yet."
            return

        source_report_path = Path(self.project.report_path)
        if not source_report_path.exists():
            QMessageBox.warning(self, "報告未找到", f"報告檔案無法在以下位置找到: {source_report_path}")
            # Original English: "Report Not Found", f"The report file could not be found at: {source_report_path}"
            return

        # Suggest a filename based on the project name or original report filename
        project_name_safe = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in self.project.name)
        # Ensure it's not empty and ends with .md
        if not project_name_safe.strip():
            project_name_safe = "Untitled_Project"
        
        suggested_filename = f"{project_name_safe}_report.md"
        if not suggested_filename.endswith(".md"):  # Should be true by construction but good check
            suggested_filename += ".md"

        target_file_path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            "將報告另存為…",  # "Save Report As..."
            str(Path.home() / suggested_filename),  # Default path and filename
            "Markdown 檔案 (*.md);;所有檔案 (*.*)"  # "Markdown Files (*.md);;All Files (*.*)" - using *.* for all files
        )

        if not target_file_path_str:
            # User cancelled the dialog
            return

        target_file_path = Path(target_file_path_str)
        # Ensure the target path has a .md extension if user didn't type one and selected "All Files"
        # However, QFileDialog usually handles this based on the selected filter.
        # If "Markdown Files (*.md)" is selected, it should enforce .md.
        # If user typed "report" and chose "All files", it might be "report".
        # Let's ensure it has an extension if none was provided and filter was generic.
        if not target_file_path.suffix and selected_filter == "所有檔案 (*.*)":
            # If user explicitly chose "All files" and typed no extension, default to .md
            # This behavior might be debated; often, "All files" means "as is".
            # For simplicity, we'll let the user manage this if they use "All files".
            # QFileDialog itself might append the default extension of the selected filter.
            pass

        try:
            shutil.copyfile(source_report_path, target_file_path)
            QMessageBox.information(self, "報告已匯出", f"報告已成功匯出至: {target_file_path}")
            # Original English: "Report Exported", f"Report successfully exported to: {target_file_path}"
        except Exception as e:
            logger.error(f"Error exporting report for project {self.project.name} to {target_file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "匯出錯誤", f"無法匯出報告: {e}")
            # Original English: "Export Error", f"Could not export report: {e}"
