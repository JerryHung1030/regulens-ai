from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel, # Added QLabel
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import Signal

from .settings import Settings
from .translator import Translator
from .utils.theme_manager import get_available_themes
from .logger import logger


class SettingsDialog(QDialog):
    """Modern, tab‑based settings editor used by MainWindow.

    The dialog directly manipulates a :class:`~app.settings.Settings` instance
    so that other application components receive the updated values
    immediately *after* the user presses **Save** (we emit the built‑in
    ``accepted`` signal).
    """

    settings_saved = Signal()

    def __init__(self, settings: Settings, translator: Translator, parent=None) -> None:  # noqa: D401  – Qt style
        super().__init__(parent)
        # Title set in _retranslate_ui
        self.settings = settings
        self.translator = translator
        
        # Store labels for retranslation
        self.general_labels = {}
        self.models_labels = {}
        self.retrieval_labels = {}
        self.output_labels = {}

        self._init_ui() # Builds UI, including initial text from translator
        self._load()    # Loads settings into UI elements

        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui() # Set initial translated text

    def _retranslate_ui(self):
        self.setWindowTitle(self.translator.get("settings_dialog_title", "Settings"))
        
        self.tabs.setTabText(0, self.translator.get("settings_tab_general", "General"))
        self.tabs.setTabText(1, self.translator.get("settings_tab_models", "Models"))
        self.tabs.setTabText(2, self.translator.get("settings_tab_retrieval", "Retrieval"))
        self.tabs.setTabText(3, self.translator.get("settings_tab_output", "Output"))

        # Update labels in General tab
        if self.general_app_theme_label:
            self.general_app_theme_label.setText(self.translator.get("settings_label_app_theme", "Application Theme:"))

        # Update labels and buttons in Models tab
        if self.models_api_key_label:
            self.models_api_key_label.setText(self.translator.get("settings_label_openai_api_key", "OpenAI API Key:"))
        if self.models_timeout_label:
            self.models_timeout_label.setText(self.translator.get("settings_label_openai_timeout", "OpenAI Client Timeout (s):"))
        if self.models_embedding_label:
            self.models_embedding_label.setText(self.translator.get("settings_label_embedding_model", "Embedding Model:"))
        # if self.models_llm_label: # Removed
        #     self.models_llm_label.setText(self.translator.get("settings_label_llm_model", "LLM Model:"))
        if hasattr(self, 'models_model_need_check_label'): # New
            self.models_model_need_check_label.setText(self.translator.get("settings_label_model_need_check", "LLM Model for Need-Check:"))
        if hasattr(self, 'models_model_audit_plan_label'): # New
            self.models_model_audit_plan_label.setText(self.translator.get("settings_label_model_audit_plan", "LLM Model for Audit Plan:"))
        if hasattr(self, 'models_model_judge_label'): # New
            self.models_model_judge_label.setText(self.translator.get("settings_label_model_judge", "LLM Model for Judge:"))
        if self.models_local_path_label:
            self.models_local_path_label.setText(self.translator.get("settings_label_local_model_path", "Local Model Path (Optional):"))
        if hasattr(self, 'local_model_button') and self.local_model_button:
            self.local_model_button.setText(self.translator.get("settings_button_browse", "Browse..."))

        # Update labels in Retrieval tab
        # if self.retrieval_top_k_label: # Removed
        #     self.retrieval_top_k_label.setText(self.translator.get("settings_label_top_k_proc", "Top-K Procedure Matches:"))
        # if self.retrieval_top_m_label: # Removed
        #     self.retrieval_top_m_label.setText(self.translator.get("settings_label_top_m_evid", "Top-M Evidence Matches:"))
        # if self.retrieval_score_thresh_label: # Removed
        #     self.retrieval_score_thresh_label.setText(self.translator.get("settings_label_score_thresh", "Score Threshold (Match Filtering):"))
        if hasattr(self, 'retrieval_audit_top_k_label'): # New
            self.retrieval_audit_top_k_label.setText(self.translator.get("settings_label_audit_top_k", "Audit Retrieval Top-K:"))


        # Update labels and buttons in Output tab
        # if self.output_report_theme_label: # Removed
        #     self.output_report_theme_label.setText(self.translator.get("settings_label_report_theme_css", "Report Theme CSS:"))
        # if hasattr(self, 'report_theme_button') and self.report_theme_button: # Removed
        #     self.report_theme_button.setText(self.translator.get("settings_button_browse_css", "Browse CSS..."))
        if self.output_report_lang_label:
            self.output_report_lang_label.setText(self.translator.get("settings_label_report_language", "Report Language:"))
        
        logger.debug("SettingsDialog UI retranslated")

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _init_ui(self) -> None:
        self.tabs = QTabWidget(self) # Store self.tabs
        self.tabs.addTab(self._build_general_tab(), self.translator.get("settings_tab_general", "General"))
        self.tabs.addTab(self._build_models_tab(), self.translator.get("settings_tab_models", "Models"))
        self.tabs.addTab(self._build_retrieval_tab(), self.translator.get("settings_tab_retrieval", "Retrieval"))
        self.tabs.addTab(self._build_output_tab(), self.translator.get("settings_tab_output", "Output"))

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        # TODO: Translate Save/Cancel buttons if not handled by Qt locale
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    # ----- per‑tab builders ------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)

        self.theme_combo = QComboBox()
        try:
            themes = get_available_themes()
            if "light" in themes: themes.remove("light")
            if "dark" in themes: themes.remove("dark")
            themes = ["light", "dark"] + sorted(themes) + ["system"]
            self.theme_combo.addItems(themes)
        except Exception as e:
            logger.error(f"Error loading themes: {e}")
            self.theme_combo.addItems(["light", "dark", "system"])
        
        self.general_app_theme_label = QLabel(self.translator.get("settings_label_app_theme", "Application Theme:"))
        layout.addRow(self.general_app_theme_label, self.theme_combo)
        
        container = QWidget()
        container.setLayout(layout)
        return container

    def _build_models_tab(self) -> QWidget:
        page_layout = QFormLayout()

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.models_api_key_label = QLabel(self.translator.get("settings_label_openai_api_key", "OpenAI API Key:"))
        page_layout.addRow(self.models_api_key_label, self.key_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.models_timeout_label = QLabel(self.translator.get("settings_label_openai_timeout", "OpenAI Client Timeout (s):"))
        page_layout.addRow(self.models_timeout_label, self.timeout_spin)

        self.embedding_model_combo = QComboBox()
        self.embedding_model_combo.addItems(["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"])
        self.models_embedding_label = QLabel(self.translator.get("settings_label_embedding_model", "Embedding Model:"))
        page_layout.addRow(self.models_embedding_label, self.embedding_model_combo)

        self.model_need_check_edit = QLineEdit()
        self.models_model_need_check_label = QLabel("LLM Model for Need-Check:") # i18n key: settings_label_model_need_check
        page_layout.addRow(self.models_model_need_check_label, self.model_need_check_edit)

        self.model_audit_plan_edit = QLineEdit()
        self.models_model_audit_plan_label = QLabel("LLM Model for Audit Plan:") # i18n key: settings_label_model_audit_plan
        page_layout.addRow(self.models_model_audit_plan_label, self.model_audit_plan_edit)

        self.model_judge_edit = QLineEdit()
        self.models_model_judge_label = QLabel("LLM Model for Judge:") # i18n key: settings_label_model_judge
        page_layout.addRow(self.models_model_judge_label, self.model_judge_edit)
        
        local_model_layout = QHBoxLayout()
        self.local_model_path_edit = QLineEdit()
        local_model_layout.addWidget(self.local_model_path_edit)
        self.local_model_button = QPushButton(self.translator.get("settings_button_browse", "Browse..."))
        self.local_model_button.clicked.connect(self._browse_local_model_path)
        local_model_layout.addWidget(self.local_model_button)
        self.models_local_path_label = QLabel(self.translator.get("settings_label_local_model_path", "Local Model Path (Optional):"))
        page_layout.addRow(self.models_local_path_label, local_model_layout)

        container = QWidget()
        container.setLayout(page_layout)
        return container

    def _build_retrieval_tab(self) -> QWidget:
        page_layout = QFormLayout()

        # self.top_k_proc_spin = QSpinBox() # Removed
        # self.top_k_proc_spin.setRange(1, 25) # Removed
        # self.retrieval_top_k_label = QLabel(self.translator.get("settings_label_top_k_proc", "Top-K Procedure Matches:")) # Removed
        # page_layout.addRow(self.retrieval_top_k_label, self.top_k_proc_spin) # Removed

        # self.top_m_evid_spin = QSpinBox() # Removed
        # self.top_m_evid_spin.setRange(1, 25) # Removed
        # self.retrieval_top_m_label = QLabel(self.translator.get("settings_label_top_m_evid", "Top-M Evidence Matches:")) # Removed
        # page_layout.addRow(self.retrieval_top_m_label, self.top_m_evid_spin) # Removed

        # self.score_thresh_spin = QDoubleSpinBox() # Removed
        # self.score_thresh_spin.setDecimals(2) # Removed
        # self.score_thresh_spin.setRange(0.0, 1.0) # Removed
        # self.score_thresh_spin.setSingleStep(0.05) # Removed
        # self.retrieval_score_thresh_label = QLabel(self.translator.get("settings_label_score_thresh", "Score Threshold (Match Filtering):")) # Removed
        # page_layout.addRow(self.retrieval_score_thresh_label, self.score_thresh_spin) # Removed
        
        self.audit_top_k_spin = QSpinBox()
        self.audit_top_k_spin.setRange(1, 25)
        self.retrieval_audit_top_k_label = QLabel("Audit Retrieval Top-K:") # i18n key: settings_label_audit_top_k
        page_layout.addRow(self.retrieval_audit_top_k_label, self.audit_top_k_spin)

        container = QWidget()
        container.setLayout(page_layout)
        return container

    def _build_output_tab(self) -> QWidget:
        page_layout = QFormLayout()

        # report_theme_layout = QHBoxLayout() # Removed
        # self.report_theme_edit = QLineEdit() # Removed
        # report_theme_layout.addWidget(self.report_theme_edit) # Removed
        # self.report_theme_button = QPushButton(self.translator.get("settings_button_browse_css", "Browse CSS...")) # Removed
        # self.report_theme_button.clicked.connect(self._browse_report_theme) # Removed
        # report_theme_layout.addWidget(self.report_theme_button) # Removed
        # self.output_report_theme_label = QLabel(self.translator.get("settings_label_report_theme_css", "Report Theme CSS:")) # Removed
        # page_layout.addRow(self.output_report_theme_label, report_theme_layout) # Removed

        self.language_combo = QComboBox()
        self.language_combo.addItems(["en", "zh"])
        self.output_report_lang_label = QLabel(self.translator.get("settings_label_report_language", "Report Language:"))
        page_layout.addRow(self.output_report_lang_label, self.language_combo)
        
        container = QWidget()
        container.setLayout(page_layout)
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
        current_theme_value = s.get("theme", "system")
        # 確保 theme_combo 中有 system 選項
        if "system" not in [self.theme_combo.itemText(i).lower() for i in range(self.theme_combo.count())]:
            self.theme_combo.addItem("system")
        self.theme_combo.setCurrentText(current_theme_value)

        # Models Tab
        self.key_edit.setText(s.get("openai.api_key", "")) # Ensure key matches new config_default structure
        self.timeout_spin.setValue(int(s.get("openai.timeout", 60))) # Ensure key matches
        self.embedding_model_combo.setCurrentText(s.get("embedding_model", "text-embedding-3-large"))
        # self.llm_model_combo.setCurrentText(s.get("llm_model", "gpt-4o")) # Removed
        self.model_need_check_edit.setText(s.get("llm.model_need_check", "gpt-4o"))
        self.model_audit_plan_edit.setText(s.get("llm.model_audit_plan", "gpt-4o"))
        self.model_judge_edit.setText(s.get("llm.model_judge", "gpt-4o"))
        self.local_model_path_edit.setText(s.get("local_model_path", ""))

        # Retrieval Tab
        # self.top_k_proc_spin.setValue(int(s.get("top_k_procedure", 5))) # Removed
        # self.top_m_evid_spin.setValue(int(s.get("top_m_evidence", 5))) # Removed
        # self.score_thresh_spin.setValue(float(s.get("score_threshold", 0.7))) # Removed
        self.audit_top_k_spin.setValue(int(s.get("audit.retrieval_top_k", 5)))


        # Output Tab
        # self.report_theme_edit.setText(s.get("report_theme", "default.css")) # Removed
        self.language_combo.setCurrentText(s.get("language", "en"))

    def _save(self):
        s = self.settings

        # General Tab
        selected_theme = self.theme_combo.currentText().lower()
        s.set("theme", selected_theme)

        # Models Tab
        s.set("openai.api_key", self.key_edit.text().strip()) # Ensure key matches new config_default structure
        s.set("openai.timeout", self.timeout_spin.value()) # Ensure key matches
        s.set("embedding_model", self.embedding_model_combo.currentText())
        
        # selected_llm = self.llm_model_combo.currentText() # Removed
        # s.set("llm_model", selected_llm) # Removed
        s.set("llm.model_need_check", self.model_need_check_edit.text().strip())
        s.set("llm.model_audit_plan", self.model_audit_plan_edit.text().strip())
        s.set("llm.model_judge", self.model_judge_edit.text().strip())
        
        s.set("local_model_path", self.local_model_path_edit.text().strip())

        # Retrieval Tab
        # s.set("top_k_procedure", self.top_k_proc_spin.value()) # Removed
        # s.set("top_m_evidence", self.top_m_evid_spin.value()) # Removed
        # s.set("score_threshold", round(self.score_thresh_spin.value(), 2)) # Removed
        s.set("audit.retrieval_top_k", self.audit_top_k_spin.value())
        
        # Output Tab
        # s.set("report_theme", self.report_theme_edit.text().strip()) # Removed
        s.set("language", self.language_combo.currentText())

        new_lang = self.language_combo.currentText()
        language_changed = self.translator.set_language(new_lang)
        if language_changed:
            logger.info(f"Translator language set to {new_lang}. MainWindow and its components will need UI refresh.")

        self.settings_saved.emit()
        self.accept()
