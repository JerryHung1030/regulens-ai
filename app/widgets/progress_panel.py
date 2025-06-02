from qtpy.QtWidgets import QDialog, QProgressBar, QTextEdit, QPushButton, QLabel, QVBoxLayout
from qtpy.QtCore import Qt, Signal


class ProgressPanel(QDialog):
    cancelled = Signal()
    completed = Signal()  # To be emitted by MainWindow when the task is truly done

    def __init__(self, parent=None, total_stages=0):  # total_stages might not be strictly needed
        super().__init__(parent)

        self.setWindowTitle("Pipeline Progress")
        self.setWindowModality(Qt.WindowModal)

        # UI Elements
        self.current_stage_label = QLabel("Initializing...")
        self.progress_bar = QProgressBar()
        self.details_text_edit = QTextEdit()
        self.details_text_edit.setReadOnly(True)
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

        # Store total_stages if needed, though update_progress takes it too
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
        self._total_stages = total_stages  # Update if it changes
        
        # Update QLabel for current stage
        current_stage_display_text = f"Stage {stage_idx}/{total_stages}: {stage_msg}"
        self.current_stage_label.setText(current_stage_display_text)

        # Update QProgressBar
        if percent < 0:
            self.progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)

        # Append stage message to QTextEdit
        self.details_text_edit.append(current_stage_display_text)

    def _handle_cancel(self):
        self._user_cancelled = True
        self.cancelled.emit()
        self.reject()  # Close the dialog

    def closeEvent(self, event):
        """
        Handle the close event. If the user closes the dialog (e.g., Esc, X button),
        emit the cancelled signal.
        """
        if not self._user_cancelled:  # If not already cancelled by the button
            # Check if the close was initiated by user action (e.g. window X button)
            # This is a bit tricky, as reject() also triggers closeEvent.
            # We use _user_cancelled to distinguish.
            # A more robust way might involve checking event.spontaneous(),
            # but for now, this should work with the current logic.
            # If the task completes, MainWindow will call self.accept() or self.close()
            # and we don't want to emit cancelled in that case.
            
            # For now, let's assume any close not via _handle_cancel is a user action
            # if the dialog is still visible.
            # However, the primary way to cancel is the button.
            # If the window's X is clicked, it's equivalent to a cancel.
            self.cancelled.emit()
        super().closeEvent(event)

    # Optional: A method to call when the process is fully completed by the worker
    # This would typically be called by the MainWindow
    def mark_completed(self):
        self.completed.emit()
        self.accept()  # Closes the dialog with QDialog.Accepted
