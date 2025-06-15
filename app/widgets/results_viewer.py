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
    QSizePolicy
)
from PySide6.QtCore import Signal, Qt
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


class RunEvidenceDetailsDialog(QDialog):
    """
    New dialog to display details from ProjectRunData:
    ControlClause text, AuditTask sentence, top_k evidence, and judge reasoning.
    """
    def __init__(self, clause: ControlClause, task: Optional[AuditTask], parent: QWidget | None = None):
        super().__init__(parent)
        self.clause = clause
        self.task = task

        clause_title_display = clause.metadata.get('title', clause.id)
        dialog_title = f"Details: {clause_title_display}"
        if task:
            dialog_title += f" / Task: {task.id}"
        self.setWindowTitle(self.tr("run_evidence_details_title", dialog_title))
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # Control Clause Text
        clause_label = QLabel(f"<b>{self.tr('control_clause_heading', 'Control Clause:')} {clause.id} - {clause_title_display}</b>")
        layout.addWidget(clause_label)
        clause_text_edit = QPlainTextEdit(clause.text)
        clause_text_edit.setReadOnly(True)
        clause_text_edit.setFixedHeight(100) # Adjust as needed
        layout.addWidget(clause_text_edit)

        if self.task:
            task_label = QLabel(f"<b>{self.tr('audit_task_heading', 'Audit Task:')} {self.task.id}</b>")
            layout.addWidget(task_label)
            task_sentence_edit = QPlainTextEdit(self.task.sentence)
            task_sentence_edit.setReadOnly(True)
            task_sentence_edit.setFixedHeight(80) # Adjust as needed
            layout.addWidget(task_sentence_edit)

            # Display Top K Evidence
            if self.task.top_k:
                evidence_heading_label = QLabel(f"<b>{self.tr('retrieved_evidence_heading', 'Retrieved Evidence (Top K):')}</b>")
                layout.addWidget(evidence_heading_label)

                evidence_text_parts = []
                for i, ev_item in enumerate(self.task.top_k):
                    score_val = ev_item.get('score', 0.0)
                    score_str = f"{score_val:.4f}" if isinstance(score_val, float) else str(score_val)

                    source_pdf = elide_text(ev_item.get('source_pdf', 'N/A'), 30)
                    page_no = ev_item.get('page_no', 'N/A')
                    excerpt = elide_text(ev_item.get('excerpt', 'N/A'), 200) # Longer excerpt for dialog

                    evidence_item_html = (
                        f"<b>{self.tr('evidence_item_label', 'Evidence')} {i+1}:</b> "
                        f"{self.tr('score_label', 'Score')}: {score_str}<br>"
                        f"&nbsp;&nbsp;{self.tr('source_label', 'Source')}: {source_pdf} ({self.tr('page_label', 'Page')}: {page_no})<br>"
                        f"&nbsp;&nbsp;{self.tr('excerpt_label', 'Excerpt')}: \"<i>{excerpt}</i>\""
                    )
                    evidence_text_parts.append(evidence_item_html)

                evidence_display_label = QLabel("<br><br>".join(evidence_text_parts))
                evidence_display_label.setTextFormat(Qt.RichText) # Enable HTML rendering
                evidence_display_label.setWordWrap(True)
                evidence_display_label.setAlignment(Qt.AlignTop)
                # Potentially add QScrollArea if evidence can be very long
                layout.addWidget(evidence_display_label)
            else:
                no_evidence_label = QLabel(f"<i>{self.tr('no_evidence_found_message', 'No evidence found for this task.')}</i>")
                no_evidence_label.setTextFormat(Qt.RichText)
                layout.addWidget(no_evidence_label)

            # Display Judge Reasoning
            reasoning = self.task.metadata.get('judge_reasoning', self.tr('reasoning_not_available', 'N/A'))
            compliant_status_text = "N/A"
            if self.task.compliant is True: compliant_status_text = self.tr("compliant_true_status", "Compliant")
            elif self.task.compliant is False: compliant_status_text = self.tr("compliant_false_status", "Non-Compliant")
            else: compliant_status_text = self.tr("compliant_pending_status", "Pending")

            reasoning_label = QLabel(f"<b>{self.tr('compliance_status_heading', 'Compliance Status:')}</b> {compliant_status_text}<br>"
                                     f"<b>{self.tr('llm_reasoning_heading', 'LLM Reasoning:')}</b><br><i>{reasoning}</i>")
            reasoning_label.setTextFormat(Qt.RichText)
            reasoning_label.setWordWrap(True)
            reasoning_label.setAlignment(Qt.AlignTop)
            layout.addWidget(reasoning_label)

        layout.addStretch() # Push elements to top

        ok_button = QPushButton(self.tr("ok_button_text", "OK"))
        ok_button.clicked.connect(self.accept)

        btn_h_layout = QHBoxLayout()
        btn_h_layout.addStretch()
        btn_h_layout.addWidget(ok_button)
        layout.addLayout(btn_h_layout)

        self.resize(700, 600)


class EvidenceDetailsDialog(QDialog): # Old dialog, kept for now
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
        txt_suggestion_text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)  # Fixed word wrap mode
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
    # STATUS_COLOR_MAP and STATUS_TEXT_COLOR removed

    def __init__(self, project: CompareProject, parent: QWidget | None = None):
        super().__init__(parent)
        logger.info(f"Initializing ResultsViewer for project: {project.name}")
        self.project = project
        # self.project.project_run_data will be loaded/set in _refresh or by MainWindow
        self._build_ui() # This will now build the table structure
        self.project.changed.connect(self._refresh)
        logger.debug("ResultsViewer initialization completed")

    # _display_name and _get_display_name methods are removed for now.
    # They might be reintroduced or adapted if needed for specific data display like clause titles.
    # _build_tab_for_proc method is removed.

    def _show_evidence_details_dialog(self, clause_id: str, task_id: Optional[str]):
        """Shows a dialog with details for the selected clause/task using RunEvidenceDetailsDialog."""
        logger.debug(f"Showing details for Control Clause ID: {clause_id}, Task ID: {task_id}")
        
        if not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            QMessageBox.warning(self, "Data Error", "Project run data not loaded.")
            return

        target_clause: Optional[ControlClause] = None
        for c_idx, c_val in enumerate(self.project.project_run_data.control_clauses):
            if c_val.id == clause_id:
                target_clause = c_val
                break
        
        if not target_clause:
            QMessageBox.warning(self, "Data Error", f"Control Clause {clause_id} not found.")
            return

        target_task: Optional[AuditTask] = None
        if task_id:
            for t_idx, t_val in enumerate(target_clause.tasks):
                if t_val.id == task_id:
                    target_task = t_val
                    break
            if not target_task:
                 QMessageBox.warning(self, "Data Error", f"Audit Task {task_id} not found in clause {clause_id}.")
                 return
        
        # Use the new RunEvidenceDetailsDialog
        dialog = RunEvidenceDetailsDialog(clause=target_clause, task=target_task, parent=self)
        dialog.exec_() # Modal dialog


    def _build_ui(self):
        logger.debug("Building ResultsViewer UI (Table Layout)")
        layout = self.layout()
        if layout: # Clear existing layout
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget: widget.deleteLater()
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(15, 15, 15, 15) # Adjusted margins
        lay.setSpacing(10) # Adjusted spacing

        title_row = QHBoxLayout()
        self._title = QLabel(f"<h2>{self.tr('analysis_results_title', 'Analysis Results')}</h2>")
        title_row.addWidget(self._title)
        title_row.addStretch(1)

        self.btn_export_csv = QPushButton(self.tr("export_csv_button", "Export Result CSV..."))
        self.btn_export_csv.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        # Connect to _export_result_csv later when it's defined
        # For now, connect to a placeholder or the old method to avoid startup error
        self.btn_export_csv.clicked.connect(self._export_result_csv) # Connect to the actual export method
        title_row.addWidget(self.btn_export_csv)

        btn_back = QPushButton(self.tr("back_to_edit_button", "Back to Edit"))
        btn_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        btn_back.clicked.connect(self._go_back)
        title_row.addWidget(btn_back)
        lay.addLayout(title_row)

        # Statistics Summary Section
        summary_layout = QHBoxLayout()
        self.summary_total_controls_label = QLabel("<b>Total Controls:</b> N/A")
        self.summary_requires_procedure_label = QLabel("<b>Requires Procedure:</b> N/A")
        self.summary_compliant_label = QLabel("<b>Compliant:</b> N/A")
        self.summary_non_compliant_label = QLabel("<b>Non-Compliant:</b> N/A")
        self.summary_pending_label = QLabel("<b>Pending:</b> N/A")
        
        summary_layout.addWidget(self.summary_total_controls_label)
        summary_layout.addSpacing(20) # Add some spacing between stats
        summary_layout.addWidget(self.summary_requires_procedure_label)
        summary_layout.addSpacing(20)
        summary_layout.addWidget(self.summary_compliant_label)
        summary_layout.addSpacing(20)
        summary_layout.addWidget(self.summary_non_compliant_label)
        summary_layout.addSpacing(20)
        summary_layout.addWidget(self.summary_pending_label)
        summary_layout.addStretch(1) # Push stats to the left
        lay.addLayout(summary_layout)
        lay.addSpacing(10) # Add some spacing before the table

        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.column_headers = [
            self.tr("col_control_id", "Control ID"),
            self.tr("col_control_title", "Control Title"),
            self.tr("col_requires_procedure", "Requires Procedure?"),
            self.tr("col_audit_task", "Audit Task"),
            self.tr("col_compliance_status", "Compliance Status"),
            self.tr("col_details", "Details")
        ]
        self.table_widget.setColumnCount(len(self.column_headers))
        self.table_widget.setHorizontalHeaderLabels(self.column_headers)

        # Define the font used for table items (consistent with what's used in _refresh)
        item_font = get_font(size=10) # Assuming size 10 is used for items
        
        # Calculate default row height
        fm = QFontMetrics(item_font)
        # Adjust padding as needed (e.g., 10 pixels total for top/bottom margin)
        default_row_height = fm.height() + 10 
        self.table_widget.verticalHeader().setDefaultSectionSize(default_row_height)
        
        # Optional: Hide the vertical header (row numbers) for a cleaner look
        self.table_widget.verticalHeader().setVisible(False)

        # self.table_widget.doubleClicked.connect(self._handle_table_double_click) # Disconnected, details button is primary
        lay.addWidget(self.table_widget)

        self.setLayout(lay)
        logger.debug("ResultsViewer UI building completed. Calling initial _refresh.")
        self._refresh()

    def _handle_table_double_click(self, model_index):
        # This method might be removed or repurposed if double-click is no longer needed.
        # For now, it's disconnected in _build_ui.
        # If re-enabled, ensure it correctly extracts clause_id and task_id from the new table structure.
        logger.debug(f"Table double-clicked at row {model_index.row()}, but action is disabled.")
        pass # Or show a message, or reactivate with updated logic.


    def _go_back(self):
        logger.info("Back button clicked, emitting edit_requested signal")
        self.edit_requested.emit(self.project)

    def _refresh(self):
        logger.info("Refreshing ResultsViewer (Table Display)")
        if self.project:
            self._title.setText(f"<h2>{self.tr('analysis_results_title', 'Analysis Results')} for: {self.project.name}</h2>")
        else:
            self._title.setText(f"<h2>{self.tr('analysis_results_title', 'Analysis Results')}</h2>")
            self.summary_total_controls_label.setText("<b>Total Controls:</b> 0")
            self.summary_requires_procedure_label.setText("<b>Requires Procedure:</b> 0")
            self.summary_compliant_label.setText("<b>Compliant:</b> 0")
            self.summary_non_compliant_label.setText("<b>Non-Compliant:</b> 0")
            self.summary_pending_label.setText("<b>Pending:</b> 0")

        self.table_widget.setRowCount(0) # Clear the table

        if not self.project or not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            logger.info("No project_run_data to display yet.")
            self.summary_total_controls_label.setText("<b>Total Controls:</b> 0")
            self.summary_requires_procedure_label.setText("<b>Requires Procedure:</b> 0")
            self.summary_compliant_label.setText("<b>Compliant:</b> 0")
            self.summary_non_compliant_label.setText("<b>Non-Compliant:</b> 0")
            self.summary_pending_label.setText("<b>Pending:</b> 0")
            
            self.table_widget.setRowCount(1)
            item = QTableWidgetItem(self.tr("no_data_available", "No analysis data available. Please run the pipeline."))
            item.setTextAlignment(Qt.AlignCenter)
            table_font = get_font(size=10) # Get font for table items
            item.setFont(table_font)
            self.table_widget.setItem(0, 0, item)
            self.table_widget.setSpan(0, 0, 1, len(self.column_headers))
            return

        # Initialize statistics counters
        table_font = get_font(size=10) # Get font for table items
        total_controls = 0
        requires_procedure_count = 0
        compliant_count = 0
        non_compliant_count = 0
        pending_count = 0

        current_row = 0
        for clause in self.project.project_run_data.control_clauses:
            # logger.debug(f"ResultsViewer: Attempting to insert row: {current_row} for clause: {clause.id}")
            self.table_widget.insertRow(current_row)
            # logger.debug(f"ResultsViewer: Successfully inserted row: {current_row}")

            total_controls += 1
            if clause.need_procedure:
                requires_procedure_count += 1
            
            if clause.tasks:
                for task in clause.tasks: # Should typically be one task
                    if task.compliant is True:
                        compliant_count += 1
                    elif task.compliant is False:
                        non_compliant_count += 1
                    else: # task.compliant is None
                        pending_count += 1
            
            # Col 0: Control ID
            item_clause_id = QTableWidgetItem(clause.id)
            item_clause_id.setFont(table_font)
            self.table_widget.setItem(current_row, 0, item_clause_id)
            # logger.debug(f"ResultsViewer: Set item for row {current_row}, col 0, text: '{item_clause_id.text()}'")

            # Col 1: Control Title - Use clause.title if available, otherwise elided clause.text
            # Assuming clause.title is already populated in the model, otherwise use clause.text
            control_title_text = clause.title if clause.title else clause.text
            item_control_title = QTableWidgetItem(elide_text(control_title_text, max_length=70))
            item_control_title.setFont(table_font)
            self.table_widget.setItem(current_row, 1, item_control_title)
            # logger.debug(f"ResultsViewer: Set item for row {current_row}, col 1, text: '{item_control_title.text()}'")

            # Col 2: Requires Procedure? (Badge)
            item_requires_proc = QTableWidgetItem()
            item_requires_proc.setTextAlignment(Qt.AlignCenter)
            item_requires_proc.setFont(table_font)
            if clause.need_procedure is True:
                item_requires_proc.setText(self.tr("yes", "Yes"))
                item_requires_proc.setBackground(QColor("#e6f7ff")) # Light blue
                item_requires_proc.setForeground(QColor("black"))
            elif clause.need_procedure is False:
                item_requires_proc.setText(self.tr("no", "No"))
                item_requires_proc.setBackground(QColor("#f0f0f0")) # Light gray
                item_requires_proc.setForeground(QColor("black"))
            else:
                item_requires_proc.setText(self.tr("n_a", "N/A"))
            self.table_widget.setItem(current_row, 2, item_requires_proc)
            # logger.debug(f"ResultsViewer: Set item for row {current_row}, col 2, text: '{item_requires_proc.text()}'")
            
            # Process tasks (should be one or none)
            task = clause.tasks[0] if clause.tasks else None

            # Col 3: Audit Task
            item_audit_task = QTableWidgetItem(elide_text(task.sentence, max_length=70) if task else self.tr("n_a", "N/A"))
            item_audit_task.setFont(table_font)
            self.table_widget.setItem(current_row, 3, item_audit_task)
            # logger.debug(f"ResultsViewer: Set item for row {current_row}, col 3, text: '{item_audit_task.text()}'")

            # Col 4: Compliance Status (Badge)
            item_compliance_status = QTableWidgetItem()
            item_compliance_status.setTextAlignment(Qt.AlignCenter)
            item_compliance_status.setFont(table_font)
            if task:
                if task.compliant is True:
                    item_compliance_status.setText(self.tr("compliant_true", "Compliant"))
                    item_compliance_status.setBackground(QColor("#d4edda")) # Light green
                    item_compliance_status.setForeground(QColor("#155724")) # Dark green text
                elif task.compliant is False:
                    item_compliance_status.setText(self.tr("compliant_false", "Non-Compliant"))
                    item_compliance_status.setBackground(QColor("#f8d7da")) # Light red
                    item_compliance_status.setForeground(QColor("#721c24")) # Dark red text (almost white on very light red)
                else: # Pending
                    item_compliance_status.setText(self.tr("compliant_pending", "Pending"))
                    item_compliance_status.setBackground(QColor("#fff3cd")) # Light yellow
                    item_compliance_status.setForeground(QColor("#856404")) # Dark yellow/brown text
            else:
                item_compliance_status.setText(self.tr("n_a", "N/A"))
            self.table_widget.setItem(current_row, 4, item_compliance_status)
            # logger.debug(f"ResultsViewer: Set item for row {current_row}, col 4, text: '{item_compliance_status.text()}'")

            # Col 5: Details Button
            details_button = QPushButton(self.tr("view_details_button", "View Details"))
            # details_button.setFont(table_font) # Optionally set font for button text too
            current_task_id = task.id if task else None
            details_button.clicked.connect(
                lambda checked=False, c_id=clause.id, t_id=current_task_id: self._show_evidence_details_dialog(c_id, t_id)
            )
            if not task:
                pass 
            
            # logger.debug(f"ResultsViewer: Attempting to set cell widget (details button) for row {current_row}, column 5")
            self.table_widget.setCellWidget(current_row, 5, details_button)
            # logger.debug(f"ResultsViewer: Successfully set cell widget for row {current_row}, column 5")
            
            # logger.debug(f"ResultsViewer: Finished processing clause {clause.id}, current_row is now {current_row + 1}")
            current_row += 1

        self.table_widget.resizeColumnsToContents()
        # logger.debug(f"ResultsViewer: Finished populating. Table actual rowCount: {self.table_widget.rowCount()}, expected rows based on current_row variable: {current_row}")
        # Adjust column stretching
        if self.table_widget.columnCount() > 1: # Control Title
            self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        if self.table_widget.columnCount() > 3: # Audit Task
            self.table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        
        # Update summary labels
        self.summary_total_controls_label.setText(f"<b>Total Controls:</b> {total_controls}")
        self.summary_requires_procedure_label.setText(f"<b>Requires Procedure:</b> {requires_procedure_count}")
        self.summary_compliant_label.setText(f"<b>Compliant:</b> {compliant_count}")
        self.summary_non_compliant_label.setText(f"<b>Non-Compliant:</b> {non_compliant_count}")
        self.summary_pending_label.setText(f"<b>Pending:</b> {pending_count}")
        
        logger.info(f"ResultsViewer table populated with {current_row} rows. Statistics updated.")

        # self.table_widget.resizeRowsToContents() # Commented out as per requirement
        self.table_widget.viewport().update()
        # logger.debug("ResultsViewer: Successfully called viewport().update().") # Removing this specific diagnostic log


    def _export_result_csv(self):
        if not self.project or not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            QMessageBox.warning(self,
                                self.tr("no_data_to_export_title", "No Data to Export"),
                                self.tr("no_data_to_export_message", "Project run data is not loaded or available. Cannot export CSV."))
            return

        # 使用更安全的文件名生成方式
        project_name_safe = re.sub(r'[^\w\s-]', '', self.project.name)  # 移除特殊字符
        project_name_safe = re.sub(r'[-\s]+', '_', project_name_safe).strip('-_')  # 將空格和連字符轉換為底線
        if not project_name_safe.strip():
            project_name_safe = "Untitled_Project"

        # 添加時間戳以避免文件名衝突
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_filename = f"{project_name_safe}_audit_results_{timestamp}.csv"

        target_file_path_str, selected_filter = QFileDialog.getSaveFileName(
            self,
            self.tr("save_csv_dialog_title", "Save Result CSV As..."),
            str(Path.home() / suggested_filename),
            self.tr("save_csv_dialog_filter", "CSV Files (*.csv);;All Files (*.*)")
        )

        if not target_file_path_str:
            return # User cancelled

        target_file_path = Path(target_file_path_str)
        
        # 確保目標目錄存在
        target_file_path.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "project_name",
            "control_clause_id", "control_clause_title", "control_clause_text",
            "requires_procedure",
            "audit_task_id", "audit_task_sentence",
            "compliant", "judge_reasoning",
            "evidence_source_pdf", "evidence_excerpt", "evidence_page_number", "evidence_score"
        ]

        max_retries = 3
        retry_delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                with open(target_file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers, quoting=csv.QUOTE_ALL)
                    writer.writeheader()

                    for clause in self.project.project_run_data.control_clauses:
                        clause_title = clause.metadata.get("title", "")
                        requires_procedure = str(clause.need_procedure) if clause.need_procedure is not None else ""
                        
                        base_row_data = {
                            "project_name": self.project.name,
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
                                    self.tr("csv_exported_dialog_title", "CSV Exported"),
                                    self.tr("csv_exported_dialog_message", "Results successfully exported to: {filepath}").format(filepath=target_file_path))
                return  # 成功導出，退出函數

            except IOError as e:
                logger.error(f"IOError exporting CSV for project {self.project.name} to {target_file_path}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    continue
                QMessageBox.critical(self,
                                 self.tr("export_error_dialog_title", "Export Error"),
                                 self.tr("export_error_dialog_message_csv", "Could not write CSV file: {error}\n\nPlease try saving to a different location.").format(error=e))
            except Exception as e:
                logger.error(f"Unexpected error during CSV export for project {self.project.name}: {e}", exc_info=True)
                QMessageBox.critical(self,
                                 self.tr("export_error_dialog_title", "Export Error"),
                                 self.tr("unexpected_export_error_dialog_message", "An unexpected error occurred during CSV export: {error}").format(error=e))
                return

    # Old _export_report method, to be replaced by _export_result_csv
    # def _export_report(self):
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
