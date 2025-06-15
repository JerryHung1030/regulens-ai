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
from PySide6.QtGui import QTextOption

from app.models.project import CompareProject
# Models from assessments and old pipeline structure are no longer directly used here
# from app.models.assessments import PairAssessment, TripleAssessment # Removed
from app.models.docs import ControlClause, AuditTask # For type hinting in new dialog
from app.pipeline.pipeline_v1_1 import ProjectRunData, _load_run_json # For loading results
from app.logger import logger


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

        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.column_headers = [
            self.tr("col_clause_id", "Control Clause ID"),
            self.tr("col_clause_title", "Control Clause Title"),
            self.tr("col_requires_proc", "Requires Procedure?"),
            self.tr("col_task_id", "Audit Task ID"),
            self.tr("col_task_sentence", "Audit Task Sentence"),
            self.tr("col_compliant", "Compliant?")
        ]
        self.table_widget.setColumnCount(len(self.column_headers))
        self.table_widget.setHorizontalHeaderLabels(self.column_headers)

        self.table_widget.doubleClicked.connect(self._handle_table_double_click) # Connect double click
        lay.addWidget(self.table_widget)

        self.setLayout(lay)
        logger.debug("ResultsViewer UI building completed. Calling initial _refresh.")
        self._refresh()

    def _handle_table_double_click(self, model_index):
        if not model_index.isValid(): return
        row = model_index.row()
        # Placeholder: Actual data retrieval from UserRole will be in _refresh's population part
        clause_id_item = self.table_widget.item(row, 0)
        task_id_item = self.table_widget.item(row, 3)

        clause_id = clause_id_item.text() if clause_id_item else "N/A" # Temporary
        task_id = task_id_item.text() if task_id_item and task_id_item.text() != "N/A" else None # Temporary

        self._show_evidence_details_dialog(clause_id, task_id)


    def _go_back(self):
        logger.info("Back button clicked, emitting edit_requested signal")
        self.edit_requested.emit(self.project)

    def _refresh(self):
        logger.info("Refreshing ResultsViewer (Table Display)")
        if self.project:
            self._title.setText(f"<h2>{self.tr('analysis_results_title', 'Analysis Results')} for: {self.project.name}</h2>")
        else:
            self._title.setText(f"<h2>{self.tr('analysis_results_title', 'Analysis Results')}</h2>")

        self.table_widget.setRowCount(0) # Clear the table

        # Data loading and table population will be implemented in the next step.
        # For now, it just shows an empty table or a message.
        if not self.project or not hasattr(self.project, 'project_run_data') or not self.project.project_run_data:
            logger.info("No project_run_data to display yet.")
            # Optionally, display a "No data" message in the table
            self.table_widget.setRowCount(1)
            item = QTableWidgetItem(self.tr("no_data_available", "No analysis data available. Please run the pipeline."))
            item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(0, 0, item)
            self.table_widget.setSpan(0, 0, 1, len(self.column_headers))
            return  # Stop further processing in _refresh if no data

        current_row = 0
        for clause in self.project.project_run_data.control_clauses:
            # clause_title = clause.metadata.get("title", clause.id)  # Use ID if title not in metadata
            clause_display_content = clause.text # Get the full text from the clause object
            elided_clause_content = elide_text(clause_display_content, max_length=100) # Elide it

            requires_proc_text = "N/A"
            if clause.need_procedure is True: requires_proc_text = self.tr("yes", "Yes")
            elif clause.need_procedure is False: requires_proc_text = self.tr("no", "No")

            if not clause.tasks:
                self.table_widget.insertRow(current_row)

                item_clause_id = QTableWidgetItem(clause.id)
                item_clause_id.setData(Qt.UserRole, clause.id)
                self.table_widget.setItem(current_row, 0, item_clause_id)

                self.table_widget.setItem(current_row, 1, QTableWidgetItem(elided_clause_content))
                self.table_widget.setItem(current_row, 2, QTableWidgetItem(requires_proc_text))

                item_task_id_na = QTableWidgetItem("N/A") # Task ID
                item_task_id_na.setData(Qt.UserRole, None) # No task ID
                self.table_widget.setItem(current_row, 3, item_task_id_na)
                self.table_widget.setItem(current_row, 4, QTableWidgetItem("N/A")) # Task Sentence
                self.table_widget.setItem(current_row, 5, QTableWidgetItem("N/A")) # Compliant
                current_row += 1
            else:
                for i, task in enumerate(clause.tasks):
                    self.table_widget.insertRow(current_row)

                    item_clause_id = QTableWidgetItem(clause.id)
                    item_clause_id.setData(Qt.UserRole, clause.id)
                    self.table_widget.setItem(current_row, 0, item_clause_id)

                    self.table_widget.setItem(current_row, 1, QTableWidgetItem(elided_clause_content))
                    self.table_widget.setItem(current_row, 2, QTableWidgetItem(requires_proc_text))

                    item_task_id = QTableWidgetItem(task.id)
                    item_task_id.setData(Qt.UserRole, task.id)
                    self.table_widget.setItem(current_row, 3, item_task_id)

                    self.table_widget.setItem(current_row, 4, QTableWidgetItem(elide_text(task.sentence, 100)))

                    compliant_text = "N/A"
                    if task.compliant is True: compliant_text = self.tr("compliant_true", "Compliant")
                    elif task.compliant is False: compliant_text = self.tr("compliant_false", "Non-Compliant")
                    else: compliant_text = self.tr("compliant_pending", "Pending")
                    self.table_widget.setItem(current_row, 5, QTableWidgetItem(compliant_text))
                    current_row += 1

        self.table_widget.resizeColumnsToContents()
        if self.table_widget.columnCount() > 1: # Ensure columns exist
            self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # Clause Title
        if self.table_widget.columnCount() > 4:
            self.table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch) # Task Sentence
        logger.info(f"ResultsViewer table populated with {current_row} rows.")


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
