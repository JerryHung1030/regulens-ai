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

from PySide6.QtCore import Signal, QCoreApplication
from PySide6.QtWidgets import QApplication

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
        
        # New Tab Order: Models, Retrieval, Output (if exists), General
        self.tabs.setTabText(0, self.translator.get("settings_tab_models", "Models"))
        self.tabs.setTabText(1, self.translator.get("settings_tab_retrieval", "Retrieval"))
        
        current_tab_offset = 2
        # Assuming self.output_tab_index is set in _init_ui if Output tab is added
        if hasattr(self, 'output_tab_index') and self.output_tab_index != -1 and self.output_tab_index < self.tabs.count():
            self.tabs.setTabText(self.output_tab_index, self.translator.get("settings_tab_output", "Output")) # Use stored index
            # The general tab would be after output if output exists, otherwise it's at index 2
            general_tab_actual_index = self.output_tab_index + 1 
            if general_tab_actual_index < self.tabs.count(): # Check if general tab index is valid
                 self.tabs.setTabText(general_tab_actual_index, self.translator.get("settings_tab_general", "General"))
        else: # Output tab doesn't exist or index is wrong
            if current_tab_offset < self.tabs.count(): # Check if general tab index is valid
                self.tabs.setTabText(current_tab_offset, self.translator.get("settings_tab_general", "General"))


        # Update labels in General tab
        if hasattr(self, 'general_app_theme_label') and self.general_app_theme_label: # Check existence
            self.general_app_theme_label.setText(self.translator.get("settings_label_app_theme", "Application Theme:"))
        if hasattr(self, 'general_gui_language_label') and self.general_gui_language_label: # New GUI language label
            self.general_gui_language_label.setText(self.translator.get("settings_label_gui_language", "GUI Language:"))

        # Update labels and buttons in Models tab
        if hasattr(self, 'models_api_key_label') and self.models_api_key_label: # Check existence
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
        # Removed: Report language label is gone from Output tab
        # if hasattr(self, 'output_report_lang_label') and self.output_report_lang_label: # Check existence
        #    self.output_report_lang_label.setText(self.translator.get("settings_label_report_language", "Report Language:"))

        save_button = self.dialog_button_box.button(QDialogButtonBox.Save)
        if save_button:
            save_button.setText(self.translator.get("save_button_text", "Save"))

        cancel_button = self.dialog_button_box.button(QDialogButtonBox.Cancel)
        if cancel_button:
            cancel_button.setText(self.translator.get("cancel_button_text", "Cancel"))
        
        logger.debug("SettingsDialog UI retranslated")

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _init_ui(self) -> None:
        self.tabs = QTabWidget(self)
        
        # New Tab Order: Models, Retrieval, General. Output tab handled conditionally.
        self.models_tab_index = 0
        self.tabs.addTab(self._build_models_tab(), self.translator.get("settings_tab_models", "Models"))
        
        self.retrieval_tab_index = 1
        self.tabs.addTab(self._build_retrieval_tab(), self.translator.get("settings_tab_retrieval", "Retrieval"))
        
        # Handle Output Tab - build it first to see if it has content
        output_tab_widget = self._build_output_tab()
        if output_tab_widget.layout() is not None and output_tab_widget.layout().count() > 0:
            self.output_tab_index = self.tabs.count() # Index at which it will be inserted
            self.tabs.addTab(output_tab_widget, self.translator.get("settings_tab_output", "Output"))
        else:
            self.output_tab_index = -1 # Mark as not present / empty

        self.general_tab_index = self.tabs.count() # General tab is added last
        self.tabs.addTab(self._build_general_tab(), self.translator.get("settings_tab_general", "General"))

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.dialog_button_box = buttons # Store instance variable
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

        self.gui_language_combo = QComboBox()
        self.gui_language_combo.addItems(["en", "zh"]) 
        self.gui_language_combo.currentTextChanged.connect(self._on_language_changed)  # 新增語言變更事件處理
        self.general_gui_language_label = QLabel(self.translator.get("settings_label_gui_language", "GUI Language:"))
        layout.addRow(self.general_gui_language_label, self.gui_language_combo)
        
        container = QWidget()
        container.setLayout(layout)
        return container

    def _on_language_changed(self, lang: str):
        """當語言變更時重新套用字體"""
        app = QCoreApplication.instance()
        if app:
            app.setProperty("language", "zh_TW" if lang == "zh" else "en_US")
            # 重新套用字體
            from app.utils.font_manager import get_display_font
            default_font = get_display_font(size=10)
            QApplication.setFont(default_font)

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
        self.models_model_need_check_label = QLabel(self.translator.get("settings_label_model_need_check", "LLM Model for Need-Check:"))
        page_layout.addRow(self.models_model_need_check_label, self.model_need_check_edit)

        self.model_audit_plan_edit = QLineEdit()
        self.models_model_audit_plan_label = QLabel(self.translator.get("settings_label_model_audit_plan", "LLM Model for Audit Plan:"))
        page_layout.addRow(self.models_model_audit_plan_label, self.model_audit_plan_edit)

        self.model_judge_edit = QLineEdit()
        self.models_model_judge_label = QLabel(self.translator.get("settings_label_model_judge", "LLM Model for Judge:"))
        page_layout.addRow(self.models_model_judge_label, self.model_judge_edit)
        
        local_model_layout = QHBoxLayout()
        self.local_model_path_edit = QLineEdit()
        local_model_layout.addWidget(self.local_model_path_edit)
        self.local_model_button = QPushButton(self.translator.get("settings_button_browse", "Browse..."))
        self.local_model_button.setObjectName("settingsButtonBrowse")
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
        self.retrieval_audit_top_k_label = QLabel(self.translator.get("settings_label_audit_top_k", "Audit Retrieval Top-K:"))
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

        # self.language_combo = QComboBox() # Removed: Language setting moved to General tab
        # self.language_combo.addItems(["en", "zh"]) # Removed
        # self.output_report_lang_label = QLabel(self.translator.get("settings_label_report_language", "Report Language:")) # Removed
        # page_layout.addRow(self.output_report_lang_label, self.language_combo) # Removed
        
        container = QWidget()
        # Only set layout if there are actual rows, otherwise it's an empty tab
        if page_layout.rowCount() > 0:
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
        if hasattr(self, 'gui_language_combo'): # Check if new combo exists
            self.gui_language_combo.setCurrentText(s.get("gui_language", "en")) # Load GUI language

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


        # Output Tab - Language setting removed
        # self.report_theme_edit.setText(s.get("report_theme", "default.css")) # Removed
        # if hasattr(self, 'language_combo') and self.language_combo: # Original language_combo for report
        #    self.language_combo.setCurrentText(s.get("language", "en")) # This was for report language

    def _save(self):
        s = self.settings

        # General Tab
        selected_theme = self.theme_combo.currentText().lower()
        s.set("theme", selected_theme)
        if hasattr(self, 'gui_language_combo'): # Check if new combo exists
            s.set("gui_language", self.gui_language_combo.currentText()) # Save GUI language

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
        
        # Output Tab - Language setting removed (original "language" key for reports is no longer set here)
        # s.set("report_theme", self.report_theme_edit.text().strip()) # Removed
        
        if hasattr(self, 'gui_language_combo'):
            new_lang = self.gui_language_combo.currentText() # Use GUI language for translator
            language_changed = self.translator.set_language(new_lang)
            if language_changed:
                logger.info(f"Translator language set to {new_lang}. Application UI will refresh.")
        # else: # Fallback if gui_language_combo somehow doesn't exist.
              # This part is probably not strictly needed if _init_ui always creates gui_language_combo.
              # old_report_lang = s.get("language", "en") # Get previously set report language if any
              # self.translator.set_language(old_report_lang) # Or set translator to a default like 'en'
              # logger.warning("gui_language_combo not found, translator language change might not reflect user's latest choice if it was made.")


        self.settings_saved.emit()
        self.accept()
