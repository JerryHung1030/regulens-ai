import logging
from typing import Optional

from qtpy.QtWidgets import QDialog, QProgressBar, QTextEdit, QPushButton, QLabel, QVBoxLayout
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QFont, QFontMetrics, QTextOption

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
        self.details_text_edit = QTextEdit()
        self.details_text_edit.setReadOnly(True)
        self.details_text_edit.setWordWrapMode(QTextOption.WordWrap)  # Ensure word wrap
        font_details = QFont()
        font_details.setPointSize(9)  # Slightly smaller for details
        self.details_text_edit.setFont(font_details)

        self.cancel_button = QPushButton("Cancel")

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.current_stage_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.details_text_edit)
        layout.addWidget(self.cancel_button)
        self.setLayout(layout)

        # Connections
        self.cancel_button.clicked.connect(self._handle_cancel)

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

    def update_progress(self, progress: float, message: str): # Signature matches pipeline_v1_1 callback
        """
        Updates the progress display based on float progress (0.0 to 1.0) and a message.
        """
        logger.debug(f"Progress update: {progress*100:.0f}% - Message: {message}")

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
        elided_details_msg = elide_long_id(
            message,
            max_length=120, # Allow longer messages in details
            font=self.details_text_edit.font(),
            width_in_pixels=self.details_text_edit.viewport().width() - 20 # Use viewport width
        )
        self.details_text_edit.append(f"[{percent_complete}%] {elided_details_msg}")


    def _handle_cancel(self):
        self._user_cancelled = True
        self.cancelled.emit()
        self.reject()  # Close the dialog

    def closeEvent(self, event):
        if not self._user_cancelled:
            self.cancelled.emit()
        super().closeEvent(event)

    def mark_completed(self):
        self.completed.emit()
        self.accept()
