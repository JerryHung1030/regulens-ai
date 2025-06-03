from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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
        # tabs.addTab(self._build_general_tab(), "General") # Removed General tab
        tabs.addTab(self._build_models_tab(), "Models")
        tabs.addTab(self._build_retrieval_tab(), "Retrieval")
        tabs.addTab(self._build_output_tab(), "Output")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ----- per‑tab builders ------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        w = QFormLayout()

        # General tab is now potentially empty or for other settings.
        # For now, let's leave it, it can be removed if it remains empty.
        # Example:
        # self.some_other_general_setting_edit = QLineEdit()
        # w.addRow("Some Other General Setting:", self.some_other_general_setting_edit)

        container = QWidget()
        container.setLayout(w)
        return container

    def _build_models_tab(self) -> QWidget:
        w = QFormLayout()

        self.key_edit = QLineEdit()  # Moved from General
        self.key_edit.setEchoMode(QLineEdit.Password)
        w.addRow("OpenAI API Key", self.key_edit)

        self.timeout_spin = QSpinBox()  # Moved from General
        self.timeout_spin.setRange(1, 300)
        w.addRow("OpenAI Client Timeout (s)", self.timeout_spin)

        self.embedding_model_combo = QComboBox()
        self.embedding_model_combo.addItems([
            "text-embedding-3-large", 
            "text-embedding-3-small", 
            "text-embedding-ada-002"
        ])
        w.addRow("Embedding Model", self.embedding_model_combo)

        self.llm_model_combo = QComboBox()
        self.llm_model_combo.addItems(["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"])
        w.addRow("LLM Model", self.llm_model_combo)
        
        local_model_layout = QHBoxLayout()
        self.local_model_path_edit = QLineEdit()
        local_model_layout.addWidget(self.local_model_path_edit)
        local_model_button = QPushButton("Browse...")
        local_model_button.clicked.connect(self._browse_local_model_path)
        local_model_layout.addWidget(local_model_button)
        w.addRow("Local Model Path (Optional)", local_model_layout)

        container = QWidget()
        container.setLayout(w)
        return container

    def _build_retrieval_tab(self) -> QWidget:
        w = QFormLayout()

        self.top_k_proc_spin = QSpinBox()
        self.top_k_proc_spin.setRange(1, 25)
        w.addRow("Top-K Procedure Matches", self.top_k_proc_spin)

        self.top_m_evid_spin = QSpinBox()
        self.top_m_evid_spin.setRange(1, 25)
        w.addRow("Top-M Evidence Matches", self.top_m_evid_spin)

        self.score_thresh_spin = QDoubleSpinBox()
        self.score_thresh_spin.setDecimals(2)
        self.score_thresh_spin.setRange(0.0, 1.0)
        self.score_thresh_spin.setSingleStep(0.05)
        w.addRow("Score Threshold (Match Filtering)", self.score_thresh_spin)
        
        container = QWidget()
        container.setLayout(w)
        return container

    def _build_output_tab(self) -> QWidget:
        w = QFormLayout()

        report_theme_layout = QHBoxLayout()
        self.report_theme_edit = QLineEdit()
        report_theme_layout.addWidget(self.report_theme_edit)
        report_theme_button = QPushButton("Browse CSS...")
        report_theme_button.clicked.connect(self._browse_report_theme)
        report_theme_layout.addWidget(report_theme_button)
        w.addRow("Report Theme CSS", report_theme_layout)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["en", "zh"])  # English, Chinese
        w.addRow("Report Language", self.language_combo)
        
        container = QWidget()
        container.setLayout(w)
        return container
        
    # --- File Dialog Helpers ---
    def _browse_local_model_path(self):
        # Could be a file or directory depending on how local models are loaded
        # For now, let's assume it could be either, or prefer directory
        path, _ = QFileDialog.getExistingDirectory(self, "Select Local Model Directory or File")
        if path:
            self.local_model_path_edit.setText(path)

    def _browse_report_theme(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Report Theme CSS File", "", "CSS Files (*.css)")
        if path:
            self.report_theme_edit.setText(path)

    # ---------------------------------------------------------------------
    # load / save helpers
    # ---------------------------------------------------------------------
    def _load(self):
        s = self.settings
        # General Tab
        self.key_edit.setText(s.get("openai_api_key", ""))  # Changed key name to be more specific
        self.timeout_spin.setValue(int(s.get("openai_client_timeout", 60)))  # Changed key name

        # Models Tab
        self.embedding_model_combo.setCurrentText(s.get("embedding_model", "text-embedding-3-large"))
        self.llm_model_combo.setCurrentText(s.get("llm_model", "gpt-4o"))
        self.local_model_path_edit.setText(s.get("local_model_path", ""))

        # Retrieval Tab
        self.top_k_proc_spin.setValue(int(s.get("top_k_procedure", 5)))
        self.top_m_evid_spin.setValue(int(s.get("top_m_evidence", 5)))
        self.score_thresh_spin.setValue(float(s.get("score_threshold", 0.7)))

        # Output Tab
        self.report_theme_edit.setText(s.get("report_theme", "default.css"))
        self.language_combo.setCurrentText(s.get("language", "en"))

    def _save(self):
        s = self.settings
        # General Tab
        s.set("openai_api_key", self.key_edit.text().strip())
        s.set("openai_client_timeout", self.timeout_spin.value())

        # Models Tab
        s.set("embedding_model", self.embedding_model_combo.currentText())
        s.set("llm_model", self.llm_model_combo.currentText())
        s.set("local_model_path", self.local_model_path_edit.text().strip())

        # Retrieval Tab
        s.set("top_k_procedure", self.top_k_proc_spin.value())
        s.set("top_m_evidence", self.top_m_evid_spin.value())
        s.set("score_threshold", round(self.score_thresh_spin.value(), 2))
        
        # Output Tab
        s.set("report_theme", self.report_theme_edit.text().strip())
        s.set("language", self.language_combo.currentText())
        
        self.accept()
