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

        self._total_stages = total_stages
        self._user_cancelled = False

    def update_progress(self, stage_idx: int, total_stages: int, stage_msg: str, percent: int):
        """
        Updates the progress display.
        - stage_idx: current stage number (1-based)
        - total_stages: total number of stages
        - stage_msg: description of the current stage
        - percent: progress percentage (0-100). If < 0, set to indeterminate.
        """
        logger.debug(f"Original stage_msg: {stage_msg} (Stage {stage_idx}/{total_stages})")
        self._total_stages = total_stages

        # Elide stage_msg for the label
        elided_label_msg = elide_long_id(
            stage_msg, 
            max_length=40,  # Character limit for label if no font
            font=self.current_stage_label.font(), 
            width_in_pixels=self.current_stage_label.width() - 20  # Approx width for label text
        )
        current_stage_display_text_for_label = f"Stage {stage_idx}/{total_stages}: {elided_label_msg}"
        self.current_stage_label.setText(current_stage_display_text_for_label)

        # Update QProgressBar
        if percent < 0:
            self.progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)

        # Elide stage_msg for the details view (can be longer)
        # For details, we might want a different max_length or rely more on font metrics if available
        elided_details_msg = elide_long_id(
            stage_msg, 
            max_length=60,  # Character limit for details if no font
            font=self.details_text_edit.font(),
            # Use a fixed width or text edit's viewport width for eliding in details
            # Using a fixed large value or relying on character length might be simpler here
            # as details_text_edit width can change.
            # For now, let's use a generous character length and the font if available.
            # If using font metrics, consider self.details_text_edit.viewport().width()
            width_in_pixels=350  # A reference width, adjust as needed
        )
        current_stage_display_text_for_details = f"Stage {stage_idx}/{total_stages}: {elided_details_msg}"
        self.details_text_edit.append(current_stage_display_text_for_details)

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
