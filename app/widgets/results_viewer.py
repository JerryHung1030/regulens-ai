from __future__ import annotations

import re
import shutil
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
    QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Signal, Qt

from app.models.project import CompareProject
from app.models.assessments import PairAssessment  # Added for type hinting
from app.logger import logger


# Helper function for eliding text if it becomes necessary (simplified version)
def elide_text(text: str | None, max_length: int = 50) -> str:
    if text is None:
        return "N/A"
    if len(text) > max_length:
        return f"{text[:max_length - 3]}..."
    return text


class ResultsViewer(QWidget):
    edit_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        logger.info(f"Initializing ResultsViewer for project: {project.name}")
        self.project = project
        self._build_ui()
        self.project.changed.connect(self._refresh)
        # Connect to updated signal if norm_map population should trigger refresh
        # self.project.updated.connect(self._refresh) # Example if needed
        logger.debug("ResultsViewer initialization completed")

    def _get_display_name(self, norm_id: str, default_prefix: str = "ID") -> str:
        """Helper to get original_filename or fallback to norm_id."""
        if not self.project or not norm_id:
            return f"{default_prefix}: N/A"
        metadata = self.project.get_norm_metadata(norm_id)
        filename = metadata.get("original_filename")
        if filename:
            return elide_text(filename, 70)  # Elide long filenames
        # Apply existing regex for shortening if it's a norm_id without filename
        short_id = re.sub(r'(norm_|procedure_|control_|evidence_|embed_set_|raw_doc_|chunk_text_|doc_)([0-9a-fA-F]{4})[0-9a-fA-F]{4,}', 
                          r'\1\2...', 
                          norm_id)
        return short_id if short_id != norm_id else norm_id

    def _render_md_for_proc(self, proc_id: str) -> str:
        logger.debug(f"Rendering markdown for procedure ID: {proc_id}")
        md_lines = []
        
        pair_assessments_for_proc: list[PairAssessment] = [
            pa for pa in self.project.get_results() if pa.procedure_doc_id == proc_id
        ]

        if not pair_assessments_for_proc:
            logger.warning(f"No assessment found for procedure ID: {proc_id}")
            return f"No assessment found for procedure ID: {proc_id}"

        for pa_idx, pa in enumerate(pair_assessments_for_proc):
            if pa_idx > 0:
                md_lines.append("\n\n---\n\n")  # Separator if multiple PairAssessments for the same procedure

            # Control Info
            control_display_name = self._get_display_name(pa.control_doc_id, "Control")
            md_lines.append(f"## Control: {control_display_name} (`{pa.control_doc_id}`)")
            
            # Procedure Info (already known by proc_id, but get its name)
            # proc_display_name = self._get_display_name(pa.procedure_doc_id, "Procedure") # proc_id is the ID
            # md_lines.append(f"### Procedure: {proc_display_name} (`{pa.procedure_doc_id}`)")
            # The tab is already named by the procedure, so focus on its assessment details

            # PairAssessment Summary
            md_lines.append(f"\n**Procedure Assessment Summary for `{self._get_display_name(pa.procedure_doc_id, 'Procedure')}`:**")
            md_lines.append(f"- **Overall Aggregated Status:** `{pa.aggregated_status}`")
            md_lines.append(f"- **Calculated Overall Score:** `{pa.overall_score if pa.overall_score is not None else 'N/A'}`")
            
            # Displaying pa.summary_analysis might still be useful if it contains LLM text not otherwise captured.
            # However, the problem is that IDs within it are not replaced.
            # For now, let's use the raw analysis if it's not empty.
            # A more advanced solution would parse this summary_analysis if it's structured (e.g. markdown itself)
            # or re-generate it here if all constituent parts are available.
            # The subtask implies replacing IDs, so we will prefer structured data over pre-formatted summary_analysis.
            
            if pa.summary_analysis and pa.summary_analysis.strip():
                md_lines.append(f"\n**Summary Analysis from Aggregation:**\n```text\n{pa.summary_analysis}\n```")

            if pa.evidence_assessments:
                md_lines.append("\n**Detailed Evidence Assessments:**")
                for i, ta in enumerate(pa.evidence_assessments):
                    evidence_doc_display_name = self._get_display_name(ta.evidence_doc_id, "Evidence Doc")
                    # evidence_chunk_id is usually a hash or part of a larger doc, may not have 'original_filename'
                    # For chunk_id, we might just display it, or if its parent (evidence_doc_id) has a name, use that.
                    # The current _get_display_name will handle norm_ids by shortening them.
                    
                    md_lines.append(f"\n#### Evidence Assessment {i + 1}")
                    md_lines.append(f"- **Evidence Document:** {evidence_doc_display_name} (`{ta.evidence_doc_id}`)")
                    md_lines.append(f"- **Evidence Chunk ID:** `{ta.evidence_chunk_id}`")  # Typically, chunk IDs don't have separate metadata
                    
                    # Displaying snippet from TripleAssessment if available, else from NormDoc.
                    # For this viewer, assuming ta.evidence_text_snippet is populated if needed.
                    # If not, we would fetch NormDoc for ta.evidence_chunk_id and get its text.
                    # metadata = self.project.get_norm_metadata(ta.evidence_chunk_id)
                    # snippet = metadata.get('text_content_snippet', 'Snippet not available.')
                    # For now, let's assume we don't have direct text snippet in TA, and focus on IDs.
                    # The report.py uses evidences_map to get text_content. We don't have that map here directly.
                    # So, we'll rely on what's in TripleAssessment.
                    
                    md_lines.append(f"  - **Status:** `{ta.status}`")
                    md_lines.append(f"  - **LLM Confidence Score:** `{ta.score if ta.score is not None else 'N/A'}`")
                    md_lines.append(f"  - **LLM Analysis:** {elide_text(ta.analysis, 200) if ta.analysis else 'N/A'}")  # Elide long analysis
                    if ta.improvement_suggestion:
                        md_lines.append(f"  - **LLM Suggestion:** {elide_text(ta.improvement_suggestion, 200)}")
            else:
                md_lines.append("\n*No individual evidence assessments provided for this procedure.*")
        
        result = "\n".join(md_lines)
        logger.debug(f"Successfully rendered markdown for procedure ID: {proc_id}")
        return result

    def _build_ui(self):
        logger.debug("Building UI for ResultsViewer")
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

        title_row = QHBoxLayout()
        self._title = QLabel(f"<h2>{self.project.name} - Comparison Results</h2>")  # Changed to English, assuming i18n is separate
        self._title.setStyleSheet("margin: 0;")
        title_row.addWidget(self._title)
        title_row.addStretch(1)

        btn_export = QPushButton("Export Report...")  # Changed to English
        btn_export.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        btn_export.setStyleSheet("""
            QPushButton { padding: 8px 16px; border-radius: 4px; background-color: #e0e0e0; border: 1px solid #cccccc; }
            QPushButton:hover { background-color: #d0d0d0; }
        """)
        btn_export.clicked.connect(self._export_report)
        title_row.addWidget(btn_export)

        btn_back = QPushButton("Back to Edit")  # Changed to English
        btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        btn_back.setStyleSheet("""
            QPushButton { padding: 8px 16px; border-radius: 4px; background-color: white; border: 1px solid #e0e0e0; }
            QPushButton:hover { background-color: #f0f0f0; }
        """)
        btn_back.clicked.connect(self._go_back)
        title_row.addWidget(btn_back)
        lay.addLayout(title_row)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e0e0e0; border-radius: 4px; background-color: white; }
            QTabBar::tab { padding: 8px 16px; margin-right: 2px; background-color: #f5f5f5; border: 1px solid #e0e0e0; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: white; border-bottom: 1px solid white; }
            QTabBar::tab:hover { background-color: #e0e0e0; }
        """)
        lay.addWidget(self.tabs)
        logger.debug("UI building completed, calling initial refresh")
        self._refresh()

    def _go_back(self):
        logger.info("Back button clicked, emitting edit_requested signal")
        self.edit_requested.emit(self.project)

    def _refresh(self):
        logger.info("Starting UI refresh for ResultsViewer")
        try:
            if self.project:
                self._title.setText(f"<h2>{self.project.name} - Comparison Results</h2>")  # Changed to English
            else:
                self._title.setText("<h2>Comparison Results</h2>")  # Changed to English

            new_proc_ids = set()
            if self.project:
                new_proc_ids = {pa.procedure_doc_id for pa in self.project.get_results()}
            
            logger.info(f"Rebuilding tabs for {len(new_proc_ids)} procedures.")
            while self.tabs.count() > 0:
                widget = self.tabs.widget(0)
                if widget:
                    self.tabs.removeTab(0)
                    widget.deleteLater()

            if not new_proc_ids:
                logger.info("No results to display, showing placeholder")
                no_results_label = QLabel("No results to display. Please run the comparison first.")  # Changed to English
                no_results_label.setAlignment(Qt.AlignCenter)
                self.tabs.addTab(no_results_label, "-")
                return

            tab_counter = 1
            sorted_pids = sorted(list(new_proc_ids))

            for pid in sorted_pids:
                try:
                    viewer = QTextBrowser()
                    viewer.setOpenExternalLinks(True)  # Verified
                    
                    markdown_content = self._render_md_for_proc(pid)
                    viewer.setMarkdown(markdown_content)

                    tab_title = pid 
                    if self.project:  # Ensure project exists
                        metadata = self.project.get_norm_metadata(pid)
                        original_filename = metadata.get("original_filename")
                        if original_filename:
                            tab_title = elide_text(original_filename)  # Elide long filenames
                        else:
                            # Fallback if original_filename is not in metadata
                            tab_title = f"Procedure {tab_counter} ({elide_text(pid, 15)})" 
                    else:  # Fallback if project somehow becomes None
                        tab_title = f"Procedure {tab_counter}"
                    
                    self.tabs.addTab(viewer, tab_title)
                    tab_counter += 1
                    logger.debug(f"Successfully created tab for procedure ID: {pid} with title {tab_title}")
                except Exception as e:
                    logger.error(f"Error creating tab for procedure {pid}: {str(e)}")
                    # Add a placeholder tab on error to maintain tab count if necessary
                    error_label = QLabel(f"Error loading procedure {pid}:\n{str(e)}")
                    error_label.setAlignment(Qt.AlignCenter)
                    self.tabs.addTab(error_label, f"Error: {elide_text(pid, 15)}")
                    tab_counter += 1

            logger.info("ResultsViewer UI refresh completed successfully")
        except Exception as e:
            logger.error(f"Error during ResultsViewer UI refresh: {str(e)}", exc_info=True)
            # raise # Re-raising might crash the app; consider logging and showing error in UI

    def _export_report(self):
        if not self.project or not self.project.report_path:
            QMessageBox.warning(self, "No Report", "The report for this project is not available or has not been generated yet.")  # English
            return

        source_report_path = Path(self.project.report_path)
        if not source_report_path.exists():
            QMessageBox.warning(self, "Report Not Found", f"The report file could not be found at: {source_report_path}")  # English
            return

        project_name_safe = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in self.project.name)
        if not project_name_safe.strip():
            project_name_safe = "Untitled_Project"
        
        suggested_filename = f"{project_name_safe}_report.md"

        target_file_path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Report As...",  # English
            str(Path.home() / suggested_filename),
            "Markdown Files (*.md);;All Files (*.*)"  # English
        )

        if not target_file_path_str:
            return

        target_file_path = Path(target_file_path_str)
        try:
            shutil.copyfile(source_report_path, target_file_path)
            QMessageBox.information(self, "Report Exported", f"Report successfully exported to: {target_file_path}")  # English
        except Exception as e:
            logger.error(f"Error exporting report for project {self.project.name} to {target_file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"Could not export report: {e}")  # English
