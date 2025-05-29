from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
)

from .settings import Settings


class SettingsDialog(QDialog):
    """Modern, tab‑based settings editor used by MainWindow.

    The dialog directly manipulates a :class:`~app.settings.Settings` instance
    so that other application components receive the updated values
    immediately *after* the user presses **Save** (we emit the built‑in
    ``accepted`` signal).
    """

    def __init__(self, settings: Settings, parent=None) -> None:  # noqa: D401  – Qt style
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings
        self._init_ui()
        self._load()

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _init_ui(self) -> None:
        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_rag_tab(), "RAG")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ----- per‑tab builders ------------------------------------------------
    def _build_general_tab(self):
        w = QFormLayout()

        self.base_edit = QLineEdit()
        w.addRow("Base URL", self.base_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        w.addRow("OpenAI API Key", self.key_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        w.addRow("Timeout (s)", self.timeout_spin)

        # wrap the form into QWidget for QTabWidget
        container = QDialog()  # lightweight widget
        container.setLayout(w)
        return container

    def _build_rag_tab(self):
        w = QFormLayout()

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["forward", "reverse", "both"])
        w.addRow("Direction", self.dir_combo)

        self.k_spin = QSpinBox()
        self.k_spin.setRange(1, 20)
        w.addRow("rag_k", self.k_spin)

        self.th_spin = QDoubleSpinBox()
        self.th_spin.setDecimals(2)
        self.th_spin.setRange(0.0, 1.0)
        self.th_spin.setSingleStep(0.05)
        w.addRow("Threshold", self.th_spin)

        container = QDialog()
        container.setLayout(w)
        return container

    # ---------------------------------------------------------------------
    # load / save helpers
    # ---------------------------------------------------------------------
    def _load(self):
        s = self.settings
        self.base_edit.setText(s.get("base_url", ""))
        self.key_edit.setText(s.get("api_key", ""))
        self.timeout_spin.setValue(int(s.get("timeout", 30)))

        self.dir_combo.setCurrentText(s.get("rag.direction", "both"))
        self.k_spin.setValue(int(s.get("rag.rag_k", 5)))
        self.th_spin.setValue(float(s.get("rag.cof_threshold", 0.5)))

    def _save(self):
        s = self.settings
        s.set("base_url", self.base_edit.text().strip())
        s.set("api_key", self.key_edit.text().strip())
        s.set("timeout", self.timeout_spin.value())

        s.set("rag.direction", self.dir_combo.currentText())
        s.set("rag.rag_k", self.k_spin.value())
        s.set("rag.cof_threshold", round(self.th_spin.value(), 2))

        self.accept() 