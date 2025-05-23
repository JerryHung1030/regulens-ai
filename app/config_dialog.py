from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
)
from PySide6.QtCore import QSettings

from .api_client import ApiClient


class ConfigDialog(QDialog):
    """Dialog for editing API and logging configuration."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = QSettings("regulens", "Regulens-AI")
        self._init_ui()
        self._load()

    def _init_ui(self) -> None:
        layout = QFormLayout(self)

        self.base_edit = QLineEdit()
        layout.addRow("Base URL", self.base_edit)

        self.key_edit = QLineEdit()
        layout.addRow("API Key", self.key_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        layout.addRow("Timeout", self.timeout_spin)

        self.log_combo = QComboBox()
        self.log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        layout.addRow("Log Level", self.log_combo)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        self.test_btn = QPushButton("Test connection")
        self.test_btn.clicked.connect(self._test_connection)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.test_btn)
        btn_row.addStretch()
        layout.addRow(btn_row)
        layout.addRow(btns)

    def _load(self) -> None:
        self.base_edit.setText(self.settings.value("base_url", ""))
        self.key_edit.setText(self.settings.value("api_key", ""))
        self.timeout_spin.setValue(int(self.settings.value("timeout", 30)))
        level = self.settings.value("log_level", "INFO")
        idx = self.log_combo.findText(level)
        if idx != -1:
            self.log_combo.setCurrentIndex(idx)

    def accept(self) -> None:  # type: ignore[override]
        self.settings.setValue("base_url", self.base_edit.text())
        self.settings.setValue("api_key", self.key_edit.text())
        self.settings.setValue("timeout", self.timeout_spin.value())
        self.settings.setValue("log_level", self.log_combo.currentText())
        super().accept()

    def _test_connection(self) -> None:
        client = ApiClient(
            self.base_edit.text(),
            self.key_edit.text(),
            timeout=self.timeout_spin.value(),
        )
        try:
            client.compare({}, {})
        except Exception as exc:
            QMessageBox.critical(self, "Connection Failed", str(exc))
        else:
            QMessageBox.information(self, "Success", "Connection succeeded")

