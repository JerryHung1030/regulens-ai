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
        self.tabs.setTabText(1, self.translator.get("settings_tab_general", "General"))
        
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

        if hasattr(self, 'retrieval_audit_top_k_label'): # New
            self.retrieval_audit_top_k_label.setText(self.translator.get("settings_label_audit_top_k", "Audit Retrieval Top-K:"))


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
        # 只保留 Models 與 General，移除 Retrieval
        self.models_tab_index = 0
        self.tabs.addTab(self._build_models_tab(), self.translator.get("settings_tab_models", "Models"))
        self.general_tab_index = self.tabs.count()
        self.tabs.addTab(self._build_general_tab(), self.translator.get("settings_tab_general", "General"))
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.dialog_button_box = buttons
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
        # 新增檢索引擎下拉式選單
        self.retrieval_engine_combo = QComboBox()
        self.retrieval_engine_combo.addItems(["FAISS"])
        self.models_retrieval_engine_label = QLabel(self.translator.get("settings_label_retrieval_engine", "Retrieval Engine:"))
        page_layout.addRow(self.models_retrieval_engine_label, self.retrieval_engine_combo)
        # Audit Top-K
        self.audit_top_k_spin = QSpinBox()
        self.audit_top_k_spin.setRange(1, 25)
        self.retrieval_audit_top_k_label = QLabel(self.translator.get("settings_label_audit_top_k", "Audit Retrieval Top-K:"))
        page_layout.addRow(self.retrieval_audit_top_k_label, self.audit_top_k_spin)
        # LLM Model Need-Check
        self.model_need_check_combo = QComboBox()
        self.model_need_check_combo.addItems(["gpt-4o"])
        self.models_model_need_check_label = QLabel(self.translator.get("settings_label_model_need_check", "LLM Model for Need-Check:"))
        page_layout.addRow(self.models_model_need_check_label, self.model_need_check_combo)
        # LLM Model Audit Plan
        self.model_audit_plan_combo = QComboBox()
        self.model_audit_plan_combo.addItems(["gpt-4o"])
        self.models_model_audit_plan_label = QLabel(self.translator.get("settings_label_model_audit_plan", "LLM Model for Audit Plan:"))
        page_layout.addRow(self.models_model_audit_plan_label, self.model_audit_plan_combo)
        # LLM Model Judge
        self.model_judge_combo = QComboBox()
        self.model_judge_combo.addItems(["gpt-4o"])
        self.models_model_judge_label = QLabel(self.translator.get("settings_label_model_judge", "LLM Model for Judge:"))
        page_layout.addRow(self.models_model_judge_label, self.model_judge_combo)
        # Local Model Path
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
        if "system" not in [self.theme_combo.itemText(i).lower() for i in range(self.theme_combo.count())]:
            self.theme_combo.addItem("system")
        self.theme_combo.setCurrentText(current_theme_value)
        if hasattr(self, 'gui_language_combo'):
            self.gui_language_combo.setCurrentText(s.get("gui_language", "en"))
        # Models Tab
        self.key_edit.setText(s.get("openai.api_key", ""))
        self.timeout_spin.setValue(int(s.get("openai.timeout", 60)))
        self.embedding_model_combo.setCurrentText(s.get("embedding_model", "text-embedding-3-large"))
        self.retrieval_engine_combo.setCurrentText(s.get("retrieval_engine", "FAISS"))
        self.audit_top_k_spin.setValue(int(s.get("audit.retrieval_top_k", 5)))
        self.model_need_check_combo.setCurrentText(s.get("llm.model_need_check", "gpt-4o"))
        self.model_audit_plan_combo.setCurrentText(s.get("llm.model_audit_plan", "gpt-4o"))
        self.model_judge_combo.setCurrentText(s.get("llm.model_judge", "gpt-4o"))
        self.local_model_path_edit.setText(s.get("local_model_path", ""))

    def _save(self):
        s = self.settings
        # General Tab
        selected_theme = self.theme_combo.currentText().lower()
        s.set("theme", selected_theme)
        if hasattr(self, 'gui_language_combo'):
            s.set("gui_language", self.gui_language_combo.currentText())
        # Models Tab
        s.set("openai.api_key", self.key_edit.text().strip())
        s.set("openai.timeout", self.timeout_spin.value())
        s.set("embedding_model", self.embedding_model_combo.currentText())
        s.set("retrieval_engine", self.retrieval_engine_combo.currentText())
        s.set("audit.retrieval_top_k", self.audit_top_k_spin.value())
        s.set("llm.model_need_check", self.model_need_check_combo.currentText())
        s.set("llm.model_audit_plan", self.model_audit_plan_combo.currentText())
        s.set("llm.model_judge", self.model_judge_combo.currentText())
        s.set("local_model_path", self.local_model_path_edit.text().strip())
        if hasattr(self, 'gui_language_combo'):
            new_lang = self.gui_language_combo.currentText()
            language_changed = self.translator.set_language(new_lang)
            if language_changed:
                logger.info(f"Translator language set to {new_lang}. Application UI will refresh.")
        self.settings_saved.emit()
        self.accept()
