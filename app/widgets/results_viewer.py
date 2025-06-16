from __future__ import annotations

import csv # For CSV export
# import shutil # shutil.copyfile was for old report export, not needed for CSV from data.
from pathlib import Path
from typing import Optional # For type hinting
import re # Keep re for now, might be useful for _get_display_name if that's kept/adapted

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    # QTabWidget, # Removed
    QStyle,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QPlainTextEdit,
    QSizePolicy,
    QFrame, # Added for StatsBarChart
    QScrollArea # Added for RunEvidenceDetailsDialog
)
from PySide6.QtCore import Signal, Qt, QSize # Added QSize
from PySide6.QtGui import QTextOption, QColor, QFontMetrics # Added QColor and QFontMetrics

from app.models.project import CompareProject
# Models from assessments and old pipeline structure are no longer directly used here
# from app.models.assessments import PairAssessment, TripleAssessment # Removed
from app.models.docs import ControlClause, AuditTask # For type hinting in new dialog
from app.pipeline.pipeline_v1_1 import ProjectRunData, _load_run_json # For loading results
from app.logger import logger
from app.utils.font_manager import get_font


# Helper function for eliding text
def elide_text(text: str | None, max_length: int = 50) -> str:
    if text is None:
        return "N/A"
    if len(text) > max_length:
        return f"{text[:max_length - 3]}..."
    return text

# StatsBarChart Class Definition START

class StatsBarChart(QWidget):
    def __init__(self, translator, parent: QWidget | None = None):
        super().__init__(parent)
        self.translator = translator
        self.setObjectName("statsBarChart")
        self.setFixedHeight(40) # Adjust height as needed

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2) # Spacing between segments

        self.compliant_frame = QFrame(self)
        self.compliant_frame.setProperty("status", "compliant")
        # self.compliant_frame.setObjectName("compliantBarSegment") # Alternative for QSS if property doesn't work well with themes
        # self.compliant_frame.setStyleSheet("background-color: #28a745;") # Removed
        self.compliant_label = QLabel("0", self.compliant_frame)
        self.compliant_label.setAlignment(Qt.AlignCenter)
        # self.compliant_label.setStyleSheet("color: white; font-weight: bold;") # Handled by QSS on QFrame
        compliant_layout = QHBoxLayout(self.compliant_frame)
        compliant_layout.addWidget(self.compliant_label)
        compliant_layout.setContentsMargins(5,0,5,0)
        self.compliant_frame.style().unpolish(self.compliant_frame) # Ensure style is reapplied
        self.compliant_frame.style().polish(self.compliant_frame)

        self.non_compliant_frame = QFrame(self)
        self.non_compliant_frame.setProperty("status", "non-compliant")
        # self.non_compliant_frame.setObjectName("nonCompliantBarSegment")
        # self.non_compliant_frame.setStyleSheet("background-color: #dc3545;") # Removed
        self.non_compliant_label = QLabel("0", self.non_compliant_frame)
        self.non_compliant_label.setAlignment(Qt.AlignCenter)
        # self.non_compliant_label.setStyleSheet("color: white; font-weight: bold;") # Handled by QSS
        non_compliant_layout = QHBoxLayout(self.non_compliant_frame)
        non_compliant_layout.addWidget(self.non_compliant_label)
        non_compliant_layout.setContentsMargins(5,0,5,0)
        self.non_compliant_frame.style().unpolish(self.non_compliant_frame)
        self.non_compliant_frame.style().polish(self.non_compliant_frame)

        self.pending_frame = QFrame(self)
        self.pending_frame.setProperty("status", "pending")
        self.pending_label = QLabel("0", self.pending_frame)
        self.pending_label.setAlignment(Qt.AlignCenter)
        pending_layout = QHBoxLayout(self.pending_frame)
        pending_layout.setContentsMargins(0,0,0,0) # Ensure label is within frame
        pending_layout.addWidget(self.pending_label)
        self.pending_frame.style().unpolish(self.pending_frame)
        self.pending_frame.style().polish(self.pending_frame)

        self.na_frame = QFrame(self) # New N/A frame
        self.na_frame.setProperty("status", "na") 
        # self.na_frame.setStyleSheet("background-color: #6c757d;") # Placeholder QSS will handle
        self.na_label = QLabel("0", self.na_frame)
        self.na_label.setAlignment(Qt.AlignCenter)
        # self.na_label.setStyleSheet("color: white; font-weight: bold;") # Placeholder QSS will handle
        na_layout = QHBoxLayout(self.na_frame)
        na_layout.setContentsMargins(0,0,0,0) # Ensure label is within frame
        na_layout.addWidget(self.na_label)
        self.na_frame.style().unpolish(self.na_frame)
        self.na_frame.style().polish(self.na_frame)
        
        self.layout.addWidget(self.compliant_frame, 0)
        self.layout.addWidget(self.non_compliant_frame, 0)
        self.layout.addWidget(self.pending_frame, 0)
        self.layout.addWidget(self.na_frame, 0) # Add N/A frame to layout

        self._update_tooltips() # Initial tooltip setup
        self.translator.language_changed.connect(self._update_tooltips)


    def setData(self, compliant_count: int, non_compliant_count: int, pending_count: int, na_count: int, total_relevant_count: int):
        self.compliant_label.setText(str(compliant_count))
        self.non_compliant_label.setText(str(non_compliant_count))
        self.pending_label.setText(str(pending_count))
        self.na_label.setText(str(na_count)) # Set N/A count

        if total_relevant_count == 0:
            self.layout.setStretchFactor(self.compliant_frame, 1) # Show one segment as placeholder
            self.layout.setStretchFactor(self.non_compliant_frame, 0)
            self.layout.setStretchFactor(self.pending_frame, 0)
            self.layout.setStretchFactor(self.na_frame, 0)
            
            self.compliant_frame.setVisible(True) 
            self.compliant_label.setText(self.translator.get("stats_bar_no_data", "No data"))
            self.non_compliant_frame.setVisible(False)
            self.pending_frame.setVisible(False)
            self.na_frame.setVisible(False)
        else:
            self.compliant_frame.setVisible(compliant_count > 0)
            self.non_compliant_frame.setVisible(non_compliant_count > 0)
            self.pending_frame.setVisible(pending_count > 0)
            self.na_frame.setVisible(na_count > 0) # Set visibility for N/A

            self.layout.setStretchFactor(self.compliant_frame, compliant_count if compliant_count > 0 else 0)
            self.layout.setStretchFactor(self.non_compliant_frame, non_compliant_count if non_compliant_count > 0 else 0)
            self.layout.setStretchFactor(self.pending_frame, pending_count if pending_count > 0 else 0)
            self.layout.setStretchFactor(self.na_frame, na_count if na_count > 0 else 0) # Set stretch for N/A
        
        self._update_tooltips(compliant_count, non_compliant_count, pending_count, na_count)
        self.layout.activate()

    def _update_tooltips(self, compliant: int = 0, non_compliant: int = 0, pending: int = 0, na: int = 0): # Added na parameter
        self.compliant_frame.setToolTip(self.translator.get("stats_tooltip_compliant", "Compliant: {count}").format(count=compliant))
        self.non_compliant_frame.setToolTip(self.translator.get("stats_tooltip_non_compliant", "Non-Compliant: {count}").format(count=non_compliant))
        self.pending_frame.setToolTip(self.translator.get("stats_tooltip_pending", "Pending: {count}").format(count=pending))
        self.na_frame.setToolTip(self.translator.get("stats_tooltip_na", "N/A: {count}").format(count=na)) # Tooltip for N/A

# StatsBarChart Class Definition END

class RunEvidenceDetailsDialog(QDialog):
    """
    New dialog to display details from ProjectRunData:
    ControlClause text, AuditTask sentence, top_k evidence, and judge reasoning.
    """
    def __init__(self, clause: ControlClause, task: Optional[AuditTask], translator, parent: QWidget | None = None): # Added translator
        super().__init__(parent)
        self.clause = clause
        self.task = task
        self.translator = translator # Store translator

        self.clause_title_display = clause.metadata.get('title', clause.id) # Store for retranslate
        # Title set in _retranslate_ui
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(700, 550) # Set fixed dialog size

        main_dialog_layout = QVBoxLayout(self) # This is the dialog's main layout

        # Scroll Area Setup
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content_widget = QWidget() # Widget to hold all scrollable content
        content_layout = QVBoxLayout(content_widget) # Layout for the content_widget

        # Control Clause Text
        self.clause_label = QLabel() # Text set in _retranslate_ui
        content_layout.addWidget(self.clause_label)
        self.clause_text_edit = QPlainTextEdit(clause.text)
        self.clause_text_edit.setReadOnly(True)
        self.clause_text_edit.setFixedHeight(100) # Keep fixed height, it has its own scroll
        content_layout.addWidget(self.clause_text_edit)

        if self.task:
            self.task_label = QLabel() # Text set in _retranslate_ui
            content_layout.addWidget(self.task_label)
            self.task_sentence_edit = QPlainTextEdit(self.task.sentence)
            self.task_sentence_edit.setReadOnly(True)
            self.task_sentence_edit.setFixedHeight(80) # Keep fixed height
            content_layout.addWidget(self.task_sentence_edit)

            if self.task.top_k:
                self.evidence_heading_label = QLabel() # Text set in _retranslate_ui
                content_layout.addWidget(self.evidence_heading_label)
                self.evidence_display_label = QLabel() # Content set in _retranslate_ui
                self.evidence_display_label.setTextFormat(Qt.RichText)
                self.evidence_display_label.setWordWrap(True)
                self.evidence_display_label.setAlignment(Qt.AlignTop)
                content_layout.addWidget(self.evidence_display_label)
            else:
                self.no_evidence_label = QLabel() # Text set in _retranslate_ui
                self.no_evidence_label.setTextFormat(Qt.RichText)
                content_layout.addWidget(self.no_evidence_label)

            self.reasoning_label = QLabel() # Content set in _retranslate_ui
            self.reasoning_label.setTextFormat(Qt.RichText)
            self.reasoning_label.setWordWrap(True)
            self.reasoning_label.setAlignment(Qt.AlignTop)
            content_layout.addWidget(self.reasoning_label)

        content_layout.addStretch(1) # Add stretch to push content to top of scroll area
        content_widget.setLayout(content_layout) # Set the layout for the content_widget
        scroll_area.setWidget(content_widget) # Put the content_widget into the scroll_area

        main_dialog_layout.addWidget(scroll_area, 1) # Add scroll_area to the main dialog layout, allowing it to stretch

        # OK Button (outside scroll area)
        self.ok_button = QPushButton() # Text set in _retranslate_ui
        self.ok_button.clicked.connect(self.accept)

        btn_h_layout = QHBoxLayout()
        btn_h_layout.addStretch()
        btn_h_layout.addWidget(self.ok_button)
        main_dialog_layout.addLayout(btn_h_layout) # Add button layout to main_dialog_layout

        # self.resize(700, 600) # Removed as setFixedSize is used
        
        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui() # Initial translation

    def _retranslate_ui(self):
        dialog_title_key = "run_evidence_details_title_task" if self.task else "run_evidence_details_title_clause"
        default_title = f"Details: {self.clause_title_display}"
        if self.task:
            default_title += f" / Task: {self.task.id}" # Task ID is not translated
        self.setWindowTitle(self.translator.get(dialog_title_key, default_title).format(clause_title=self.clause_title_display, task_id=self.task.id if self.task else ""))

        self.clause_label.setText(f"<b>{self.translator.get('control_clause_heading', 'Control Clause:')} {self.clause.id} - {self.clause_title_display}</b>")

        if self.task:
            self.task_label.setText(f"<b>{self.translator.get('audit_task_heading', 'Audit Task:')} {self.task.id}</b>")

            if self.task.top_k:
                self.evidence_heading_label.setText(f"<b>{self.translator.get('retrieved_evidence_heading', 'Retrieved Evidence (Top K):')}</b>")
                evidence_text_parts = []
                for i, ev_item in enumerate(self.task.top_k):
                    score_val = ev_item.get('score', 0.0)
                    score_str = f"{score_val:.4f}" if isinstance(score_val, float) else str(score_val)
                    source_pdf = elide_text(ev_item.get('source_pdf', 'N/A'), 30)
                    page_no = ev_item.get('page_no', 'N/A')
                    excerpt = elide_text(ev_item.get('excerpt', 'N/A'), 200)
                    evidence_item_html = (
                        f"<b>{self.translator.get('evidence_item_label', 'Evidence')} {i+1}:</b> "
                        f"{self.translator.get('score_label', 'Score')}: {score_str}<br>"
                        f"&nbsp;&nbsp;{self.translator.get('source_label', 'Source')}: {source_pdf} ({self.translator.get('page_label', 'Page')}: {page_no})<br>"
                        f"&nbsp;&nbsp;{self.translator.get('excerpt_label', 'Excerpt')}: \"<i>{excerpt}</i>\""
                    )
                    evidence_text_parts.append(evidence_item_html)
                self.evidence_display_label.setText("<br><br>".join(evidence_text_parts))
            else:
                if hasattr(self, 'no_evidence_label'): # Check if the label was created
                    self.no_evidence_label.setText(f"<i>{self.translator.get('no_evidence_found_message', 'No evidence found for this task.')}</i>")

            reasoning = self.task.metadata.get('judge_reasoning', self.translator.get('reasoning_not_available', 'N/A'))
            compliant_status_text = "N/A" # Default, should be overwritten
            if self.task.compliant is True: compliant_status_text = self.translator.get("compliant_true_status", "Compliant")
            elif self.task.compliant is False: compliant_status_text = self.translator.get("compliant_false_status", "Non-Compliant")
            else: compliant_status_text = self.translator.get("compliant_pending_status", "Pending")
            
            if hasattr(self, 'reasoning_label'): # Check if the label was created
                self.reasoning_label.setText(f"<b>{self.translator.get('compliance_status_heading', 'Compliance Status:')}</b> {compliant_status_text}<br>"
                                         f"<b>{self.translator.get('llm_reasoning_heading', 'LLM Reasoning:')}</b><br><i>{reasoning}</i>")
        
        self.ok_button.setText(self.translator.get("ok_button_text", "OK"))
        logger.debug("RunEvidenceDetailsDialog UI retranslated")


class EvidenceDetailsDialog(QDialog): # Old dialog
    def __init__(self, evidence_data: dict, translator, parent: QWidget | None = None): # Added translator
        super().__init__(parent)
        self.evidence_data = evidence_data
        self.translator = translator # Store translator
        # Title set in _retranslate_ui
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        self.lbl_file_title = QLabel() # Text set in _retranslate_ui
        layout.addWidget(self.lbl_file_title)

        self.lbl_analysis_title = QLabel() # Text set in _retranslate_ui
        layout.addWidget(self.lbl_analysis_title)
        
        self.txt_analysis = QPlainTextEdit()
        self.txt_analysis.setPlainText(self.evidence_data.get('analysis', 'N/A'))
        self.txt_analysis.setReadOnly(True)
        self.txt_analysis.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.addWidget(self.txt_analysis)

        self.lbl_suggestion_title = QLabel() # Text set in _retranslate_ui
        layout.addWidget(self.lbl_suggestion_title)
        
        self.txt_suggestion = QPlainTextEdit()
        self.txt_suggestion.setPlainText(self.evidence_data.get('suggestion', 'N/A'))
        self.txt_suggestion.setReadOnly(True)
        # txt_suggestion_text was a typo, should be self.txt_suggestion
        self.txt_suggestion.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.addWidget(self.txt_suggestion)

        self.btn_ok = QPushButton() # Text set in _retranslate_ui
        self.btn_ok.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

        self.resize(500, 400)
        
        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui() # Initial translation

    def _retranslate_ui(self):
        self.setWindowTitle(self.translator.get("evidence_details_title", "Evidence Details"))
        self.lbl_file_title.setText(f"<b>{self.translator.get('file', 'File')}:</b> {self.evidence_data.get('evidence_display_name', 'N/A')}")
        self.lbl_analysis_title.setText(self.translator.get("analysis_label", "Analysis:"))
        self.lbl_suggestion_title.setText(self.translator.get("suggestion_label", "Suggestion:"))
        self.btn_ok.setText(self.translator.get("ok_button_text", "OK")) # Reusing ok_button_text
        logger.debug("EvidenceDetailsDialog UI retranslated")


class ResultsViewer(QWidget):
    edit_requested = Signal(CompareProject)

    def __init__(self, project: CompareProject, translator, parent: QWidget | None = None): # Added translator
        super().__init__(parent)
        logger.info(f"Initializing ResultsViewer for project: {project.name}")
        self.project = project
        self.translator = translator # Store translator
        self._build_ui()
        self.project.changed.connect(self._refresh) # _refresh will call _retranslate_ui
        
        self.translator.language_changed.connect(self._retranslate_ui)
        # _retranslate_ui() # Called by _refresh via _build_ui
        logger.debug("ResultsViewer initialization completed")

    def _show_evidence_details_dialog(self, clause_id: str, task_id: Optional[str]):
        logger.debug(f"Showing details for Control Clause ID: {clause_id}, Task ID: {task_id}")
        
        if not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            QMessageBox.warning(self, 
                                self.translator.get("data_error_title", "Data Error"), 
                                self.translator.get("project_run_data_not_loaded_text", "Project run data not loaded."))
            return

        target_clause: Optional[ControlClause] = None
        for c_idx, c_val in enumerate(self.project.project_run_data.control_clauses):
            if c_val.id == clause_id:
                target_clause = c_val
                break
        
        if not target_clause:
            QMessageBox.warning(self, 
                                self.translator.get("data_error_title", "Data Error"), 
                                self.translator.get("control_clause_not_found_text", "Control Clause {clause_id} not found.").format(clause_id=clause_id))
            return

        target_task: Optional[AuditTask] = None
        if task_id:
            for t_idx, t_val in enumerate(target_clause.tasks):
                if t_val.id == task_id:
                    target_task = t_val
                    break
            if not target_task:
                 QMessageBox.warning(self, 
                                     self.translator.get("data_error_title", "Data Error"), 
                                     self.translator.get("audit_task_not_found_text", "Audit Task {task_id} not found in clause {clause_id}.").format(task_id=task_id, clause_id=clause_id))
                 return
        
        dialog = RunEvidenceDetailsDialog(clause=target_clause, task=target_task, translator=self.translator, parent=self)
        dialog.exec_()


    def _build_ui(self):
        logger.debug("Building ResultsViewer UI (Table Layout)")
        layout = self.layout()
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget: widget.deleteLater()
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(10)

        title_row = QHBoxLayout()
        self._title = QLabel() # Text set in _retranslate_ui/_refresh
        title_row.addWidget(self._title)
        title_row.addStretch(1)

        self.btn_export_csv = QPushButton() # Text/Icon set in _retranslate_ui
        self.btn_export_csv.clicked.connect(self._export_result_csv)
        title_row.addWidget(self.btn_export_csv)

        self.btn_back = QPushButton() # Text/Icon set in _retranslate_ui
        self.btn_back.clicked.connect(self._go_back)
        title_row.addWidget(self.btn_back)
        lay.addLayout(title_row)

        # Statistics Summary Section
        summary_section_layout = QVBoxLayout() # Main container for stats rows
        
        # Row 1: Total Controls and Requires Procedure (existing labels) - TO BE REMOVED
        # top_summary_row_layout = QHBoxLayout()
        # self.summary_total_controls_label = QLabel() 
        # self.summary_requires_procedure_label = QLabel()
        # top_summary_row_layout.addWidget(self.summary_total_controls_label)
        # top_summary_row_layout.addSpacing(20)
        # top_summary_row_layout.addWidget(self.summary_requires_procedure_label)
        # top_summary_row_layout.addStretch(1)
        # summary_section_layout.addLayout(top_summary_row_layout) # REMOVED

        # Row 2: Bar Chart for Compliance Statuses (Now effectively Row 1 of summary)
        self.stats_summary_title_label = QLabel() # Title for Stats Bar Chart
        font_stats_title = self.stats_summary_title_label.font()
        font_stats_title.setPointSize(12)
        font_stats_title.setBold(True)
        self.stats_summary_title_label.setFont(font_stats_title)
        summary_section_layout.addWidget(self.stats_summary_title_label)

        self.stats_bar_chart = StatsBarChart(self.translator, self)
        summary_section_layout.addWidget(self.stats_bar_chart) # Add bar chart directly
        
        lay.addLayout(summary_section_layout)
        lay.addSpacing(10) # Existing spacing before the table

        self.detailed_results_title_label = QLabel() # Title for Detailed Results Table
        font_table_title = self.detailed_results_title_label.font()
        font_table_title.setPointSize(12)
        font_table_title.setBold(True)
        self.detailed_results_title_label.setFont(font_table_title)
        lay.addWidget(self.detailed_results_title_label)
        # lay.addSpacing(5) # Optional small spacing after title

        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Column headers set in _retranslate_ui
        self.column_headers_keys = [
            "col_control_id", "col_control_title", "col_requires_procedure",
            "col_audit_task", "col_compliance_status", "col_details"
        ]
        self.column_headers_defaults = [
            "Control ID", "Control Title", "Requires Procedure?",
            "Audit Task", "Compliance Status", "Details"
        ]
        self.table_widget.setColumnCount(len(self.column_headers_keys))
        # self.table_widget.setHorizontalHeaderLabels(...) # Done in _retranslate_ui

        item_font = get_font(size=10)
        fm = QFontMetrics(item_font)
        default_row_height = fm.height() + 10 
        self.table_widget.verticalHeader().setDefaultSectionSize(default_row_height)
        self.table_widget.verticalHeader().setVisible(False)

        lay.addWidget(self.table_widget)
        self.setLayout(lay)
        
        logger.debug("ResultsViewer UI building completed. Calling initial _refresh which includes _retranslate_ui.")
        self._refresh() # This will also call _retranslate_ui

    def _retranslate_ui(self):
        self._title.setText(f"<h2>{self.translator.get('analysis_results_title', 'Analysis Results')}</h2>")
        self.btn_export_csv.setText(self.translator.get("export_csv_button", "Export Result CSV..."))
        self.btn_export_csv.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_back.setText(self.translator.get("back_to_edit_button", "Back to Edit"))
        self.btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))

        # Retranslate column headers
        translated_headers = [self.translator.get(key, default) for key, default in zip(self.column_headers_keys, self.column_headers_defaults)]
        self.table_widget.setHorizontalHeaderLabels(translated_headers)
        
        # Refresh dynamic parts of the UI that depend on language
        self._refresh_summary_labels() # Separated logic for summary
        self._refresh_table_content_text() # For texts inside table cells that need retranslation

        # Retranslate new titles
        if hasattr(self, 'stats_summary_title_label'):
            self.stats_summary_title_label.setText(self.translator.get("results_viewer_stats_title", "Compliance Summary"))
        if hasattr(self, 'detailed_results_title_label'):
            self.detailed_results_title_label.setText(self.translator.get("results_viewer_table_title", "Detailed Results"))
            
        logger.debug("ResultsViewer UI retranslated")

    def _refresh_summary_labels(self):
        # This is called by _retranslate_ui and _refresh
        # It updates labels based on current data and current language
        total_controls = 0
        requires_procedure_count = 0
        compliant_count = 0
        non_compliant_count = 0
        pending_count = 0

        if self.project and hasattr(self.project, 'project_run_data') and self.project.project_run_data:
            for clause in self.project.project_run_data.control_clauses:
                total_controls += 1
                if clause.need_procedure:
                    requires_procedure_count += 1
                if clause.tasks:
                    for task in clause.tasks:
                        if task.compliant is True: compliant_count += 1
                        elif task.compliant is False: non_compliant_count += 1
                        else: pending_count += 1
            
            project_name = self.project.name # Project name is not translated
            self._title.setText(f"<h2>{self.translator.get('analysis_results_for_project_title', 'Analysis Results for: {project_name}').format(project_name=project_name)}</h2>")
        else:
            self._title.setText(f"<h2>{self.translator.get('analysis_results_title', 'Analysis Results')}</h2>")

        # Removed: Old text summary labels
        # self.summary_total_controls_label.setText(f"<b>{self.translator.get('summary_total_controls', 'Total Controls')}:</b> {total_controls}")
        # self.summary_requires_procedure_label.setText(f"<b>{self.translator.get('summary_requires_procedure', 'Requires Procedure')}:</b> {requires_procedure_count}")
        
        na_count = total_controls - (compliant_count + non_compliant_count + pending_count)
        if na_count < 0: na_count = 0 

        total_for_bar = total_controls 
        self.stats_bar_chart.setData(compliant_count, non_compliant_count, pending_count, na_count, total_for_bar)
        
    def _refresh_table_content_text(self):
        # This method is responsible for re-translating texts within table cells
        # if they were set with translatable strings (e.g., "Yes", "No", "N/A", status badges)
        # It assumes the table structure (rows, columns, buttons) is already there from _refresh.
        table_font = get_font(size=10)
        for row in range(self.table_widget.rowCount()):
            # Requires Procedure? (Col 2)
            item_requires_proc = self.table_widget.item(row, 2)
            if item_requires_proc: # Check if item exists
                # Re-determine original boolean value to re-translate. This is tricky.
                # Assume a data attribute was stored or re-fetch from self.project.project_run_data
                # For simplicity, this example might not perfectly re-translate existing cell content without original data.
                # A better approach: _refresh should always rebuild cells with translated text.
                # This method is more for cases where _refresh is too heavy and only text needs update.
                # Given current _refresh, this might be redundant if _refresh is called on language change.
                # However, if _refresh is NOT called, then we need to update.
                # Let's assume _refresh IS called, so this method as-is might not be strictly needed
                # unless there are other dynamic texts not covered.
                # The "View Details" button text is set in _refresh.
                # "Yes", "No", "N/A", "Compliant", "Non-Compliant", "Pending" are set in _refresh.
                pass # Most cell content is rebuilt by _refresh

        # Update "View Details" button text if it was missed by _refresh or needs specific re-translation
        for row in range(self.table_widget.rowCount()):
            button = self.table_widget.cellWidget(row, 5) # Column 5 for Details button
            if isinstance(button, QPushButton):
                button.setText(self.translator.get("view_details_button", "View Details"))


    def _handle_table_double_click(self, model_index):
        logger.debug(f"Table double-clicked at row {model_index.row()}, but action is disabled.")
        pass


    def _go_back(self):
        logger.info("Back button clicked, emitting edit_requested signal")
        self.edit_requested.emit(self.project)

    def _refresh(self):
        logger.info("Refreshing ResultsViewer (Table Display)")
        self._retranslate_ui() # Ensure all static texts are up-to-date with current language

        self.table_widget.setRowCount(0)

        if not self.project or not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            logger.info("No project_run_data to display yet.")
            # _refresh_summary_labels handles the case of no data
            
            self.table_widget.setRowCount(1)
            item = QTableWidgetItem(self.translator.get("no_data_available", "No analysis data available. Please run the pipeline."))
            item.setTextAlignment(Qt.AlignCenter)
            table_font = get_font(size=10)
            item.setFont(table_font)
            self.table_widget.setItem(0, 0, item)
            self.table_widget.setSpan(0, 0, self.table_widget.columnCount()) # Span all columns
            return

        table_font = get_font(size=10)
        current_row = 0
        for clause in self.project.project_run_data.control_clauses:
            self.table_widget.insertRow(current_row)
            
            item_clause_id = QTableWidgetItem(clause.id) # ID is not translated
            item_clause_id.setFont(table_font)
            self.table_widget.setItem(current_row, 0, item_clause_id)

            control_title_text = clause.title if clause.title else clause.text # Title/text not translated here
            item_control_title = QTableWidgetItem(elide_text(control_title_text, max_length=70))
            item_control_title.setFont(table_font)
            self.table_widget.setItem(current_row, 1, item_control_title)

            item_requires_proc = QTableWidgetItem()
            item_requires_proc.setTextAlignment(Qt.AlignCenter)
            item_requires_proc.setFont(table_font)
            if clause.need_procedure is True:
                item_requires_proc.setText(self.translator.get("yes", "Yes"))
                item_requires_proc.setBackground(QColor("#e6f7ff"))
                item_requires_proc.setForeground(QColor("black"))
            elif clause.need_procedure is False:
                item_requires_proc.setText(self.translator.get("no", "No"))
                item_requires_proc.setBackground(QColor("#f0f0f0"))
                item_requires_proc.setForeground(QColor("black"))
            else:
                item_requires_proc.setText(self.translator.get("n_a", "N/A")) # n_a already exists
            self.table_widget.setItem(current_row, 2, item_requires_proc)
            
            task = clause.tasks[0] if clause.tasks else None
            task_sentence_display = elide_text(task.sentence, max_length=70) if task else self.translator.get("n_a", "N/A")
            item_audit_task = QTableWidgetItem(task_sentence_display) # Sentence not translated here
            item_audit_task.setFont(table_font)
            self.table_widget.setItem(current_row, 3, item_audit_task)

            item_compliance_status = QTableWidgetItem()
            item_compliance_status.setTextAlignment(Qt.AlignCenter)
            item_compliance_status.setFont(table_font)
            if task:
                if task.compliant is True:
                    item_compliance_status.setText(self.translator.get("compliant_true_long", "Compliant")) # Using a potentially longer version for table
                    item_compliance_status.setBackground(QColor("#d4edda"))
                    item_compliance_status.setForeground(QColor("#155724"))
                elif task.compliant is False:
                    item_compliance_status.setText(self.translator.get("compliant_false_long", "Non-Compliant"))
                    item_compliance_status.setBackground(QColor("#f8d7da"))
                    item_compliance_status.setForeground(QColor("#721c24"))
                else:
                    item_compliance_status.setText(self.translator.get("compliant_pending_long", "Pending"))
                    item_compliance_status.setBackground(QColor("#fff3cd"))
                    item_compliance_status.setForeground(QColor("#856404"))
            else:
                item_compliance_status.setText(self.translator.get("n_a", "N/A"))
            self.table_widget.setItem(current_row, 4, item_compliance_status)

            details_button = QPushButton(self.translator.get("view_details_button", "View Details"))
            current_task_id = task.id if task else None # Task ID not translated
            details_button.clicked.connect(
                lambda checked=False, c_id=clause.id, t_id=current_task_id: self._show_evidence_details_dialog(c_id, t_id)
            )
            self.table_widget.setCellWidget(current_row, 5, details_button)
            
            current_row += 1

        self.table_widget.resizeColumnsToContents()
        if self.table_widget.columnCount() > 1:
            self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        if self.table_widget.columnCount() > 3:
            self.table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        
        logger.info(f"ResultsViewer table populated with {current_row} rows. Statistics updated via _refresh_summary_labels called from _retranslate_ui.")
        self.table_widget.viewport().update()


    def _export_result_csv(self):
        if not self.project or not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            QMessageBox.warning(self,
                                self.translator.get("no_data_to_export_title", "No Data to Export"),
                                self.translator.get("no_data_to_export_message", "Project run data is not loaded or available. Cannot export CSV."))
            return

        # 使用更安全的文件名生成方式
        project_name_safe = re.sub(r'[^\w\s-]', '', self.project.name)
        project_name_safe = re.sub(r'[-\s]+', '_', project_name_safe).strip('-_')
        if not project_name_safe.strip():
            project_name_safe = self.translator.get("untitled_project_csv_default", "Untitled_Project")

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename_key = "audit_results_csv_default_filename"
        default_filename_pattern = "{project_name}_audit_results_{timestamp}.csv"
        
        suggested_filename = self.translator.get(default_filename_key, default_filename_pattern).format(
            project_name=project_name_safe, timestamp=timestamp
        )


        target_file_path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.translator.get("save_csv_dialog_title", "Save Result CSV As..."),
            str(Path.home() / suggested_filename),
            self.translator.get("save_csv_dialog_filter", "CSV Files (*.csv);;All Files (*.*)")
        )

        if not target_file_path_str:
            return

        target_file_path = Path(target_file_path_str)
        target_file_path.parent.mkdir(parents=True, exist_ok=True)

        # CSV Headers - these should ideally be translatable if the CSV is for user consumption in different languages
        # However, for data exchange, non-translated headers are common. Assuming non-translated for now.
        headers = [
            "project_name", "control_clause_id", "control_clause_title", "control_clause_text",
            "requires_procedure", "audit_task_id", "audit_task_sentence",
            "compliant", "judge_reasoning",
            "evidence_source_pdf", "evidence_excerpt", "evidence_page_number", "evidence_score"
        ]

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                with open(target_file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers, quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                    for clause in self.project.project_run_data.control_clauses:
                        # ... (rest of CSV writing logic remains largely the same, ensure any direct strings are handled if necessary) ...
                        clause_title = clause.metadata.get("title", "")
                        requires_procedure = str(clause.need_procedure) if clause.need_procedure is not None else ""
                        base_row_data = {
                            "project_name": self.project.name, # Project name itself is not translated
                            "control_clause_id": clause.id,
                            "control_clause_title": clause_title,
                            "control_clause_text": clause.text,
                            "requires_procedure": requires_procedure,
                        }
                        if not clause.tasks:
                            row_data = base_row_data.copy()
                            for key in headers:
                                if key not in row_data: row_data[key] = ""
                            writer.writerow(row_data)
                        else:
                            for task in clause.tasks:
                                task_row_data = base_row_data.copy()
                                task_row_data.update({
                                    "audit_task_id": task.id,
                                    "audit_task_sentence": task.sentence,
                                    "compliant": str(task.compliant) if task.compliant is not None else "",
                                    "judge_reasoning": task.metadata.get("judge_reasoning", ""),
                                })
                                if not task.top_k:
                                    for key_ev in ["evidence_source_pdf", "evidence_excerpt", "evidence_page_number", "evidence_score"]:
                                        task_row_data[key_ev] = ""
                                    writer.writerow(task_row_data)
                                else:
                                    for evidence_item in task.top_k:
                                        evidence_row_data = task_row_data.copy()
                                        evidence_row_data.update({
                                            "evidence_source_pdf": evidence_item.get("source_pdf", ""),
                                            "evidence_excerpt": evidence_item.get("excerpt", ""),
                                            "evidence_page_number": str(evidence_item.get("page_no", "")),
                                            "evidence_score": f"{evidence_item.get('score', ''):.4f}" if isinstance(evidence_item.get('score'), float) else str(evidence_item.get('score', ''))
                                        })
                                        writer.writerow(evidence_row_data)
                QMessageBox.information(self,
                                    self.translator.get("csv_exported_dialog_title", "CSV Exported"),
                                    self.translator.get("csv_exported_dialog_message", "Results successfully exported to: {filepath}").format(filepath=target_file_path))
                return

            except IOError as e:
                logger.error(f"IOError exporting CSV for project {self.project.name} to {target_file_path}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    continue
                QMessageBox.critical(self,
                                 self.translator.get("export_error_dialog_title", "Export Error"),
                                 self.translator.get("export_error_dialog_message_csv", "Could not write CSV file: {error}\n\nPlease try saving to a different location.").format(error=e))
            except Exception as e:
                logger.error(f"Unexpected error during CSV export for project {self.project.name}: {e}", exc_info=True)
                QMessageBox.critical(self,
                                 self.translator.get("export_error_dialog_title", "Export Error"),
                                 self.translator.get("unexpected_export_error_dialog_message", "An unexpected error occurred during CSV export: {error}").format(error=e))
                return

    # def _export_report(self): # Old report export, can be translated similarly if reactivated
    #     if not self.project or not self.project.report_path:
    #         QMessageBox.warning(self,
    #                             self.translator.get("no_report_dialog_title", "No Report"),
    #                             self.translator.get("no_report_dialog_message", "The report for this project is not available or has not been generated yet."))
    #         return
    #     # ... rest of the logic with self.translator.get for dialogs and messages ...
