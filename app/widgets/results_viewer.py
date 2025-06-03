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
    QStyle,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QPlainTextEdit
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextOption  # For future use with opening files perhaps, Added QTextOption for text wrapping
# from PySide6.QtCore import QUrl # Duplicate import removed

import functools  # For partial function application

from app.models.project import CompareProject
from app.models.assessments import PairAssessment, TripleAssessment  # Added TripleAssessment
from app.logger import logger


# Helper function for eliding text if it becomes necessary (simplified version)
def elide_text(text: str | None, max_length: int = 50) -> str:
    if text is None:
        return "N/A"
    if len(text) > max_length:
        return f"{text[:max_length - 3]}..."
    return text


class EvidenceDetailsDialog(QDialog):
    def __init__(self, evidence_data: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.evidence_data = evidence_data
        # TODO: Use self.tr() for i18n once plumbed
        self.setWindowTitle(self.tr("evidence_details_title", "Evidence Details"))
        self.setAttribute(Qt.WA_DeleteOnClose)  # Ensure dialog is deleted when closed

        layout = QVBoxLayout(self)

        # Evidence File Name
        lbl_file_title = QLabel(f"<b>{self.tr('file', 'File')}:</b> {self.evidence_data.get('evidence_display_name', 'N/A')}")
        layout.addWidget(lbl_file_title)

        # Analysis Section
        lbl_analysis_title = QLabel(self.tr("analysis_label", "Analysis:"))
        layout.addWidget(lbl_analysis_title)
        
        txt_analysis = QPlainTextEdit()
        txt_analysis.setPlainText(self.evidence_data.get('analysis', 'N/A'))
        txt_analysis.setReadOnly(True)
        txt_analysis.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)  # Fixed word wrap mode
        layout.addWidget(txt_analysis)

        # Suggestion Section
        lbl_suggestion_title = QLabel(self.tr("suggestion_label", "Suggestion:"))
        layout.addWidget(lbl_suggestion_title)
        
        txt_suggestion = QPlainTextEdit()
        txt_suggestion.setPlainText(self.evidence_data.get('suggestion', 'N/A'))
        txt_suggestion.setReadOnly(True)
        txt_suggestion.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)  # Fixed word wrap mode
        layout.addWidget(txt_suggestion)

        # OK Button
        # TODO: Use self.tr("ok_button", "OK")
        btn_ok = QPushButton("OK") 
        btn_ok.clicked.connect(self.accept)  # QDialog.accept() closes the dialog
        
        # Add a small horizontal layout for the button to align it to the right (optional)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        self.resize(500, 400)  # Set a reasonable default size


class ResultsViewer(QWidget):
    edit_requested = Signal(CompareProject)

    STATUS_COLOR_MAP = {
        "Pass": "#2e7d32",     # Green
        "Partial": "#f9a825",  # Yellow/Orange
        "Fail": "#c62828",     # Red
        "N/A": "#546e7a",      # Gray
        "Unknown": "#546e7a"   # Default/fallback if status is unexpected
    }
    # Text color for badges, chosen for contrast with most badge colors
    STATUS_TEXT_COLOR = "white" 

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        logger.info(f"Initializing ResultsViewer for project: {project.name}")
        self.project = project
        self._build_ui()
        self.project.changed.connect(self._refresh)
        # Connect to updated signal if norm_map population should trigger refresh
        # self.project.updated.connect(self._refresh) # Example if needed
        logger.debug("ResultsViewer initialization completed")

    def _display_name(self, norm_id: str) -> str:
        """
        Gets the display name for a norm_id.
        Prefers original_filename from metadata, otherwise truncates norm_id.
        """
        if not norm_id:
            return "N/A"

        if not self.project:
            # Fallback if project is not available, though this shouldn't happen in normal use
            return f"{norm_id[:10]}..." if len(norm_id) > 10 else norm_id

        metadata = self.project.get_norm_metadata(norm_id)
        if metadata:
            original_filename = metadata.get("original_filename")
            if original_filename and original_filename.strip():
                return original_filename
        
        # Fallback to truncated norm_id
        if len(norm_id) > 10:
            return f"{norm_id[:10]}..."
        return norm_id

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

    def _build_tab_for_proc(self, proc_id: str) -> QWidget:
        logger.debug(f"Building tab for procedure ID: {proc_id}")
        
        container_widget = QWidget()
        layout = QVBoxLayout(container_widget)
        layout.setContentsMargins(10, 10, 10, 10)  # Smaller margins for tab content
        layout.setSpacing(8)

        pair_assessments_for_proc: list[PairAssessment] = []
        if self.project:
            pair_assessments_for_proc = [
                pa for pa in self.project.get_results() if pa.procedure_doc_id == proc_id
            ]

        if not pair_assessments_for_proc:
            logger.warning(f"No assessment data found for procedure ID: {proc_id}")
            # TODO: Use i18n for "No assessment data..."
            no_data_label = QLabel(f"No assessment data found for procedure: {self._display_name(proc_id)}")
            no_data_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(no_data_label)
            container_widget.setLayout(layout)
            return container_widget

        # For now, using the first PairAssessment for the summary header.
        # Future: Could aggregate or allow selecting if multiple controls map to this one procedure.
        pa = pair_assessments_for_proc[0]

        # Summary Section
        # TODO: Use i18n for labels like "Procedure:", "Control:", "Score:", "Overall Status:"
        
        # Procedure: <Name> [Overall Status]
        # TODO: Use self.tr for "Procedure:" prefix
        procedure_base_text = f"{self.tr('procedure_label', 'Procedure')}: {self._display_name(pa.procedure_doc_id)}"
        
        lbl_procedure = QLabel()
        lbl_procedure.setTextFormat(Qt.RichText)  # Allow HTML for status badge
        
        if pa.aggregated_status:
            raw_status = str(pa.aggregated_status)
            # TODO: Ensure pa.aggregated_status aligns with keys in STATUS_COLOR_MAP or handle translation if it's already translated.
            # Assuming pa.aggregated_status is one of "Pass", "Fail", etc.
            color = self.STATUS_COLOR_MAP.get(raw_status, self.STATUS_COLOR_MAP["Unknown"])
            # TODO: Use i18n for status text: self.tr(f"{raw_status.lower()}_status", raw_status)
            translated_status = self.tr(f"{raw_status.lower()}_status", raw_status)
            
            status_badge_html = (
                f"<span style=\"color: {self.STATUS_TEXT_COLOR}; background-color: {color}; "
                f"padding: 2px 5px; border-radius: 3px;\">{translated_status}</span>"
            )
            lbl_procedure.setText(f"{procedure_base_text} {status_badge_html}")
        else:
            lbl_procedure.setText(procedure_base_text)
            
        lbl_procedure.setStyleSheet("font-weight: bold; font-size: 14px;")  # TODO: Refine styles
        layout.addWidget(lbl_procedure)

        # TODO: Use self.tr for "Control:" prefix
        lbl_control = QLabel(f"{self.tr('control_label', 'Control')}: {self._display_name(pa.control_doc_id)}")
        layout.addWidget(lbl_control)
        
        score_str = f"{pa.overall_score:.2f}" if pa.overall_score is not None else "N/A"
        lbl_score = QLabel(f"Overall Score: {score_str}")
        layout.addWidget(lbl_score)

        # The aggregated status is already appended to the procedure label.
        # If a separate "Overall: <Status>" is needed:
        # lbl_overall_status = QLabel(f"Overall Status: {pa.aggregated_status}")
        # layout.addWidget(lbl_overall_status)

        # --- Evidence Table ---
        all_triple_assessments: list[TripleAssessment] = []
        for p_assess in pair_assessments_for_proc:
            if p_assess.evidence_assessments:
                all_triple_assessments.extend(p_assess.evidence_assessments)
        
        if not all_triple_assessments:
            # TODO: Use i18n
            no_evidence_label = QLabel("No evidence items for this procedure.")
            no_evidence_label.setAlignment(Qt.AlignCenter)
            no_evidence_label.setStyleSheet("font-style: italic; color: grey; padding: 10px;")
            layout.addWidget(no_evidence_label)
        else:
            table = QTableWidget()
            # TODO: Use i18n for headers: self.tr("file"), self.tr("status_header"), self.tr("score"), self.tr("details")
            headers = ["File", "Status", "Score", "Details"]
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setEditTriggers(QTableWidget.NoEditTriggers)  # Non-editable

            for row, ta in enumerate(all_triple_assessments):
                table.insertRow(row)
                
                # File
                file_item = QTableWidgetItem(self._display_name(ta.evidence_doc_id))
                table.setItem(row, 0, file_item)
                
                # Status
                raw_status = str(ta.status)  # e.g., "Pass", "Fail"
                color = self.STATUS_COLOR_MAP.get(raw_status, self.STATUS_COLOR_MAP["Unknown"])
                # TODO: Use i18n for status text: self.tr(f"{raw_status.lower()}_status", raw_status)
                translated_status_text = self.tr(f"{raw_status.lower()}_status", raw_status)

                status_html = (
                    f"<span style=\"color: {self.STATUS_TEXT_COLOR}; background-color: {color}; "
                    f"padding: 2px 5px; border-radius: 3px;\">{translated_status_text}</span>"
                )
                # status_item = QTableWidgetItem()
                # We need to set this on a QLabel inside a cell to render HTML, or use a delegate.
                # For simplicity, QTableWidgetItem doesn't directly render rich HTML like a QLabel.
                # A common workaround is to use a QLabel as the cell widget.
                # However, for simple HTML like this, setting it on a QLabel and then painting that
                # label onto the cell is overkill. Let's try setting a QLabel as cell widget.
                # This might have performance implications for very large tables.
                # A more performant way for rich text in cells is QStyledItemDelegate.
                
                # Fallback: If QLabel as cell widget is too complex for this step or has issues,
                # we might just store color data and expect styling via QPalette or delegate later.
                # For now, let's try with a simple QLabel as cell widget for the badge.
                
                status_label_for_cell = QLabel(status_html)
                status_label_for_cell.setAlignment(Qt.AlignCenter)
                status_label_for_cell.setStyleSheet("background-color: transparent;")  # Ensure label bg is transparent
                table.setCellWidget(row, 1, status_label_for_cell)
                # status_item.setTextAlignment(Qt.AlignCenter) # Alignment is on the label now
                
                # Score
                score_val = f"{ta.score:.2f}" if ta.score is not None else "N/A"
                score_item = QTableWidgetItem(score_val)
                score_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(row, 2, score_item)
                
                # Details Button
                # TODO: Use i18n for button text "🔍" or self.tr("details_button", "🔍")
                btn_details = QPushButton(self.tr("details_button", "🔍"))
                # TODO: Use i18n for tooltip: self.tr("view_evidence_details_tooltip", "View Analysis and Suggestion")
                btn_details.setToolTip(self.tr("view_evidence_details_tooltip", "View Analysis and Suggestion"))
                
                evidence_data_for_dialog = {
                    "evidence_doc_id": ta.evidence_doc_id,
                    "evidence_display_name": self._display_name(ta.evidence_doc_id),
                    "analysis": ta.analysis,
                    "suggestion": ta.improvement_suggestion,
                    "status": str(ta.status),
                    "score": score_val
                }
                # Use functools.partial to pass current `ta` data to the slot
                btn_details.clicked.connect(
                    functools.partial(self._show_evidence_details, evidence_data_for_dialog)
                )
                table.setCellWidget(row, 3, btn_details)

            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # File column
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Status
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Score
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Details
            table.verticalHeader().setVisible(False)  # Hide row numbers
            table.setMinimumHeight(150)  # Ensure table has some initial height

            layout.addWidget(table)

        layout.addStretch(1)  # Push content to the top
        container_widget.setLayout(layout)
        logger.debug(f"Successfully built tab for procedure ID: {proc_id}")
        return container_widget

    def _show_evidence_details(self, evidence_data: dict):
        logger.debug(f"Showing details for evidence: {evidence_data.get('evidence_doc_id')}")
        
        # Ensure `evidence_display_name` is present, if not already handled upstream
        if 'evidence_display_name' not in evidence_data and 'evidence_doc_id' in evidence_data:
            evidence_data['evidence_display_name'] = self._display_name(evidence_data['evidence_doc_id'])

        dialog = EvidenceDetailsDialog(evidence_data, self)
        # dialog.exec() # For modal dialog
        dialog.show()  # For modeless dialog

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
        # TODO: Hook up self.tr properly if not already available through QObject inheritance
        title_suffix = self.tr("Comparison Results", " - Comparison Results")
        self._title = QLabel(f"<h2>{title_suffix}</h2>")
        self._title.setStyleSheet("""
            QLabel {
                font-size: 16px; /* Adjusted from 20px */
                font-weight: 500; /* Medium weight */
                color: #333333; /* Standard dark text color */
                margin: 0; /* Keep existing margin */
            }
        """)
        title_row.addWidget(self._title)
        title_row.addStretch(1)

        btn_export = QPushButton(self.tr("export_report", "Export Report..."))
        btn_export.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        btn_export.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: #e8e8e8; /* Light gray, distinct from primary actions */
                border: 1px solid #cccccc;
                color: #333333;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
                border-color: #bbbbbb;
            }
            QPushButton:pressed {
                background-color: #c8c8c8;
            }
        """)
        btn_export.clicked.connect(self._export_report)
        title_row.addWidget(btn_export)

        btn_back = QPushButton(self.tr("back_to_edit", "Back to Edit"))
        btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        btn_back.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                background-color: transparent; /* Outlined button style */
                border: 1px solid #cccccc;
                color: #555555; /* Slightly lighter text */
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f0f0f0; /* Light background on hover */
                border-color: #bbbbbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        btn_back.clicked.connect(self._go_back)
        title_row.addWidget(btn_back)
        lay.addLayout(title_row)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #dcdcdc; /* Slightly softer border */
                border-top: none; /* Top border handled by TabBar or covered by it */
                border-radius: 0 0 4px 4px; /* Rounded bottom corners */
                background-color: white;
                padding: 16px; /* Add padding inside the tab pane */
            }
            QTabBar::tab {
                padding: 10px 20px; /* Increased padding for tabs */
                margin-right: 1px;
                background-color: #f0f0f0; /* Light gray for inactive tabs */
                border: 1px solid #dcdcdc;
                border-bottom: none; /* Tab border doesn't include bottom line */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #555555; /* Text color for inactive tabs */
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: white; /* Selected tab matches pane background */
                color: #1a73e8; /* Primary color for selected tab text */
                border-color: #dcdcdc;
                /* To make the selected tab appear connected to the pane,
                   its bottom border is often removed or set to the pane's background color.
                   However, QTabBar draws its own base line. We can make the selected tab
                   visually sit on top by ensuring its background is white. */
                /* For a line indicator:
                border-bottom: 3px solid #1a73e8;
                padding-bottom: 7px; /* Adjust padding to account for border */
                */
            }
            QTabBar::tab:!selected:hover {
                background-color: #e6e6e6; /* Hover for non-selected tabs */
                color: #333333;
            }
            QTabBar::tab:selected:hover {
                background-color: #fdfdfd; /* Slight hover for selected tab if needed */
            }
            QTabBar {
                /* This draws a line under the tab bar. Set to transparent or tab pane's border color */
                /* border-bottom: 1px solid #dcdcdc; */ 
                /* Alternatively, remove it if QTabWidget::pane border-top is visible and sufficient */
                /* Or use QTabBar::tear and QTabBar::scroller for more control if needed */
            }
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
            title_suffix = self.tr("Comparison Results", " - Comparison Results")
            if self.project:
                self._title.setText(f"<h2>{title_suffix}</h2>")
            else:
                # TODO: self.tr for "Comparison Results"
                self._title.setText(f"<h2>{self.tr('comparison_results_title', 'Comparison Results')}</h2>")

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
                no_results_text = self.tr("no_results_to_display", "No results to display. Please run the comparison first.")
                no_results_label = QLabel(no_results_text)
                no_results_label.setAlignment(Qt.AlignCenter)
                self.tabs.addTab(no_results_label, "-")  # Tab title "-" is fine for a single placeholder
                return

            sorted_pids = sorted(list(new_proc_ids))

            for pid in sorted_pids:
                try:
                    tab_content_widget = self._build_tab_for_proc(pid)
                    
                    procedure_display_name = self._display_name(pid)
                    # Use elide_text for the name part of the title to keep tabs from becoming too wide
                    tab_title_text = self.tr("procedure_tab_title", "Procedure: {procedure_name}").format(
                        procedure_name=elide_text(procedure_display_name, 30)  # Elide if name is too long
                    )
                    
                    self.tabs.addTab(tab_content_widget, tab_title_text)
                    logger.debug(f"Successfully created tab for procedure ID: {pid} with title {tab_title_text}")
                except Exception as e:
                    logger.error(f"Error creating tab for procedure {pid}: {str(e)}")
                    # Add a placeholder tab on error to maintain tab count if necessary
                    error_label = QLabel(f"Error loading procedure {pid}:\n{str(e)}")
                    error_label.setAlignment(Qt.AlignCenter)
                    self.tabs.addTab(error_label, f"Error: {elide_text(pid, 15)}")

            logger.info("ResultsViewer UI refresh completed successfully")
        except Exception as e:
            logger.error(f"Error during ResultsViewer UI refresh: {str(e)}", exc_info=True)
            # raise # Re-raising might crash the app; consider logging and showing error in UI

    def _export_report(self):
        if not self.project or not self.project.report_path:
            QMessageBox.warning(self, 
                                self.tr("no_report_dialog_title", "No Report"), 
                                self.tr("no_report_dialog_message", "The report for this project is not available or has not been generated yet."))
            return

        source_report_path = Path(self.project.report_path)
        if not source_report_path.exists():
            QMessageBox.warning(self, 
                                self.tr("report_not_found_dialog_title", "Report Not Found"), 
                                self.tr("report_not_found_dialog_message", "The report file could not be found at: {filepath}").format(filepath=source_report_path))
            return

        project_name_safe = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in self.project.name)
        if not project_name_safe.strip():
            project_name_safe = "Untitled_Project"
        
        suggested_filename = f"{project_name_safe}_report.md"

        target_file_path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr("save_report_dialog_title", "Save Report As..."),
            str(Path.home() / suggested_filename),
            self.tr("save_report_dialog_filter", "Markdown Files (*.md);;All Files (*.*)")
        )

        if not target_file_path_str:
            return

        target_file_path = Path(target_file_path_str)
        try:
            shutil.copyfile(source_report_path, target_file_path)
            QMessageBox.information(self, 
                                    self.tr("report_exported_dialog_title", "Report Exported"), 
                                    self.tr("report_exported_dialog_message", "Report successfully exported to: {filepath}").format(filepath=target_file_path))
        except Exception as e:
            logger.error(f"Error exporting report for project {self.project.name} to {target_file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, 
                                 self.tr("export_error_dialog_title", "Export Error"), 
                                 self.tr("export_error_dialog_message", "Could not export report: {error}").format(error=e))
