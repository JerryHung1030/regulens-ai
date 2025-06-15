import logging
from typing import Optional, Union, Any # Added Union, Any for type flexibility

from qtpy.QtWidgets import QDialog, QProgressBar, QTextEdit, QPushButton, QLabel, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QFont, QFontMetrics, QTextOption

# Import the Pydantic model for type checking
from app.pipeline.pipeline_v1_1 import AuditPlanClauseUIData # AuditTaskUIData is part of AuditPlanClauseUIData

logger = logging.getLogger(__name__)


def elide_long_id(text: str, max_length: int = 32, font: Optional[QFont] = None, width_in_pixels: int = 360) -> str:
    """
    Truncates long strings, especially those containing IDs.
    Aims to keep the first 8 characters, an ellipsis ..., and the last 8 characters
    if the string is longer than max_length.
    If a font is provided, uses QFontMetrics.elidedText for more precise truncation.
    """
    if font:
        fm = QFontMetrics(font)
        return fm.elidedText(text, Qt.ElideMiddle, width_in_pixels)
    
    if len(text) > max_length:
        if "norm_" in text or len(text) > 20:  # Heuristic for ID-like strings
            # Attempt to keep start and end for IDs
            prefix_len = 8
            suffix_len = 8
            if len(text) > prefix_len + suffix_len + 3:  # 3 for "..."
                return f"{text[:prefix_len]}...{text[-suffix_len:]}"
            else:  # If not much longer than what we want to keep, just truncate
                return f"{text[:max_length - 3]}..."
        else:  # Generic truncation for other long strings
            return f"{text[:max_length - 3]}..."
    return text


class ProgressPanel(QDialog):
    cancelled = Signal()
    audit_plan_confirmed = Signal() # New signal for audit plan confirmation
    completed = Signal()  # To be emitted by MainWindow when the task is truly done

    def __init__(self, parent=None, total_stages=0):
        super().__init__(parent)

        self.setWindowTitle("Pipeline Progress")
        self.setWindowModality(Qt.WindowModal)

        # UI Elements
        self.current_stage_label = QLabel("Initializing...")
        font_label = QFont()
        font_label.setPointSize(10)
        self.current_stage_label.setFont(font_label)

        self.progress_bar = QProgressBar()
        # self.details_text_edit = QTextEdit()
        # self.details_text_edit.setReadOnly(True)
        # self.details_text_edit.setWordWrapMode(QTextOption.WordWrap)  # Ensure word wrap
        # font_details = QFont()
        # font_details.setPointSize(9)  # Slightly smaller for details
        # self.details_text_edit.setFont(font_details)
        self.details_tree_widget = QTreeWidget()
        self.details_tree_widget.setColumnCount(1)
        self.details_tree_widget.setHeaderLabels(["Audit Plan Details"])
        font_details = QFont()
        font_details.setPointSize(9) # Slightly smaller for details
        self.details_tree_widget.setFont(font_details)


        self.confirm_button = QPushButton("Confirm and Start Checking Internal Documents")
        self.confirm_button.setEnabled(False) # Initially disabled
        self.cancel_button = QPushButton("Cancel")

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.current_stage_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.details_tree_widget) # Replaced QTextEdit with QTreeWidget
        layout.addWidget(self.confirm_button) # Added confirm button
        layout.addWidget(self.cancel_button)
        self.setLayout(layout)

        # Connections
        self.cancel_button.clicked.connect(self._handle_cancel)
        self.confirm_button.clicked.connect(self._handle_confirm) # Connect new button

        # _total_stages is not explicitly passed at init anymore, but can be set by first update_progress call
        self._user_cancelled = False
        self.pipeline_stage_names = [ # Define the new stage names
            "Initializing Pipeline", # Corresponds to progress < 0.1 (or initial message)
            "Need-Check",            # Progress 0.1 to < 0.3
            "Audit-Plan Generation", # Progress 0.3 to < 0.6
            "Evidence Search & Retrieval", # Progress 0.6 to < 0.8
            "Compliance Judgment"    # Progress 0.8 to 1.0
        ]
        self._total_stages = len(self.pipeline_stage_names) # Now 5 stages including initialization

    def update_progress(self, progress: float, message_data: object): # Signature changed: message -> message_data, str -> object
        """
        Updates the progress display based on float progress (0.0 to 1.0) and a message_data (str or AuditPlanClauseUIData).
        """
        # logger.debug(f"Progress update: {progress*100:.0f}% - Message Type: {type(message_data)}")
        if isinstance(message_data, str):
             logger.debug(f"Progress update: {progress*100:.0f}% - Message: {message_data}")
        elif isinstance(message_data, AuditPlanClauseUIData):
             logger.debug(f"Progress update: {progress*100:.0f}% - AuditPlan Data: {message_data.clause_id}")


        percent_complete = int(progress * 100)

        # Determine current stage name based on progress
        stage_name = "Unknown Stage"
        stage_idx = 0 # 0-based for list index
        if progress < 0.01 : # Initializing often sends 0.0
            stage_idx = 0
        elif 0.01 <= progress < 0.3: # Step 1: Need-Check (0.1 to 0.3 in pipeline, but callback sends overall progress)
            stage_idx = 1
        elif 0.3 <= progress < 0.6: # Step 2: Audit-Plan
            stage_idx = 2
        elif 0.6 <= progress < 0.8: # Step 3: Search
            stage_idx = 3
        elif 0.8 <= progress < 1.0: # Step 4: Judge
            stage_idx = 4
        elif progress >= 1.0:
            stage_idx = self._total_stages -1 # Last stage if progress is 1.0 or more
            percent_complete = 100 # Cap at 100

        if 0 <= stage_idx < self._total_stages:
            stage_name = self.pipeline_stage_names[stage_idx]

        current_stage_label_text = f"Current Stage: {stage_name} ({percent_complete}%)"
        self.current_stage_label.setText(current_stage_label_text)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent_complete)

        # Use the detailed message from the pipeline for the text edit
        # Elide if necessary for display, though QTextEdit handles long lines with scrolling
        # elided_details_msg = elide_long_id(
        #     message,
        #     max_length=120, # Allow longer messages in details
        #     font=self.details_tree_widget.font(), # Changed from details_text_edit
        #     width_in_pixels=self.details_tree_widget.viewport().width() - 20 # Changed from details_text_edit
        # )
        # self.details_text_edit.append(f"[{percent_complete}%] {elided_details_msg}") # This will be replaced by tree population logic

        # New logic to handle message types for QTreeWidget
        if isinstance(message_data, AuditPlanClauseUIData):
            # It's an AuditPlanClauseUIData object, use attribute access
            clause_id = message_data.clause_id
            clause_title = message_data.clause_title if message_data.clause_title else "" # Handle optional title
            
            clause_item_text = f"{clause_id}: {clause_title}"
            # Elide long clause titles if necessary
            elided_clause_text = elide_long_id(clause_item_text, max_length=100, font=self.details_tree_widget.font(), width_in_pixels=self.details_tree_widget.viewport().width() - 25) # Adjust width as needed
            clause_item = QTreeWidgetItem(self.details_tree_widget, [elided_clause_text])

            if message_data.no_audit_needed:
                QTreeWidgetItem(clause_item, ["無須制定條文"])
            elif message_data.tasks: # Check if there are tasks
                for task_obj in message_data.tasks: # task_obj is AuditTaskUIData
                    task_sentence = task_obj.sentence
                    elided_task_text = elide_long_id(task_sentence, max_length=150, font=self.details_tree_widget.font(), width_in_pixels=self.details_tree_widget.viewport().width() - 45) # Indented, so less width
                    QTreeWidgetItem(clause_item, [elided_task_text])
                clause_item.setExpanded(True) # Expand clauses with tasks
            
            self.details_tree_widget.scrollToItem(clause_item)

            # Enable confirm_button based on the audit_plan_generation_complete flag
            if message_data.audit_plan_generation_complete and self.confirm_button.text() != "Confirmed":
                 if not self.confirm_button.isEnabled(): # Only enable if not already enabled
                    self.confirm_button.setEnabled(True)
                    logger.info("Audit plan display complete. Confirm button enabled via audit_plan_generation_complete flag.")

        elif isinstance(message_data, str): # Existing behavior for string messages
            log_message = f"[{percent_complete}%] {message_data}"
            elided_log_message = elide_long_id(log_message, max_length=150, font=self.details_tree_widget.font(), width_in_pixels=self.details_tree_widget.viewport().width() - 25)
            
            item = QTreeWidgetItem(self.details_tree_widget, [elided_log_message])
            self.details_tree_widget.scrollToItem(item)
        else:
            # Handle other types or log a warning if necessary
            logger.warning(f"ProgressPanel received message of unexpected type: {type(message_data)}")

        # Old logic for enabling confirm button based on progress percentage and stage name is removed.
        # It's now driven by the `audit_plan_generation_complete` flag in AuditPlanClauseUIData.


    def _handle_cancel(self):
        self._user_cancelled = True
        self.cancelled.emit()
        self.reject()  # Close the dialog

    def _handle_confirm(self):
        """Handles the confirm button click."""
        self.audit_plan_confirmed.emit()
        self.confirm_button.setEnabled(False) # Disable after clicking
        self.confirm_button.setText("Confirmed") # Optional: Change text
        logger.info("Audit plan confirmed by user.")

    def closeEvent(self, event):
        if not self._user_cancelled:
            self.cancelled.emit()
        super().closeEvent(event)

    def mark_completed(self):
        self.completed.emit()
        self.accept()
