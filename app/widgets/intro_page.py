import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt, Signal
from ..translator import Translator # Assuming translator.py is in app/
from ..logger import logger # Assuming logger.py is in app/


class IntroPage(QWidget):
    start_requested = Signal()

    def __init__(self, translator: Translator, parent=None):
        super().__init__(parent)
        self.setObjectName("introPage")
        self.translator = translator
        self._init_ui() # Creates UI elements
        
        # Connect signal and call retranslate for initial setup
        self.translator.language_changed.connect(self._retranslate_ui)
        self._retranslate_ui()


    def _retranslate_ui(self):
        # Update subtitle
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(self.translator.get("intro_subtitle_v2", "Harness the power of AI to navigate, understand, and manage complex regulatory landscapes with unparalleled efficiency and precision.")) # Updated key
        
        # Update core pipeline section title (renamed from pipeline_card_title_label)
        if hasattr(self, 'core_pipeline_title_label'): # Renamed attribute
            self.core_pipeline_title_label.setText(self.translator.get("intro_core_pipeline_title", "Core Pipeline")) # Updated key

        # Update Get Started button
        if hasattr(self, 'get_started_button'):
            self.get_started_button.setText(self.translator.get("intro_get_started_button", "Get Started"))

        # Update Header Section
        if hasattr(self, 'title_label'):
            self.title_label.setText(self.translator.get("intro_title", "<h1>Regulens-AI</h1>")) # intro_title is still the same

        # Update Core Pipeline Section (previously Pipeline Card)
        # self.core_pipeline_title_label is already updated above
        if hasattr(self, 'pipeline_step_labels'): # Name retained for simplicity, though section is renamed
            steps_data_keys = [ # Updated keys
                ("intro_pipeline_step1_title_v2", "intro_pipeline_step1_desc_v2"),
                ("intro_pipeline_step2_title_v2", "intro_pipeline_step2_desc_v2"),
                ("intro_pipeline_step3_title_v2", "intro_pipeline_step3_desc_v2"),
                ("intro_pipeline_step4_title_v2", "intro_pipeline_step4_desc_v2")
            ]
            default_steps_text = [ # Updated default texts to match new content
                ("<strong>1. Secure Document Upload</strong>", "<small>Initiate the process by securely uploading your regulatory documents...</small>"),
                ("<strong>2. Intelligent AI Analysis</strong>", "<small>Leverage advanced AI algorithms for in-depth text extraction...</small>"),
                ("<strong>3. Actionable Insight Generation</strong>", "<small>Receive AI-powered summaries, extracted obligations...</small>"),
                ("<strong>4. Interactive Review & Export</strong>", "<small>Engage with the analyzed content through an intuitive interface...</small>")
            ]
            for i, label_pair in enumerate(self.pipeline_step_labels):
                icon_label, text_label = label_pair
                title_key, desc_key = steps_data_keys[i]
                default_title, default_desc = default_steps_text[i]
                # Icon is not translated
                translated_text = f"{self.translator.get(title_key, default_title)}<br>{self.translator.get(desc_key, default_desc)}"
                text_label.setText(translated_text)
        
        # Update Key Features Section
        if hasattr(self, 'key_features_title_label'):
            self.key_features_title_label.setText(self.translator.get("intro_key_features_title", "Key Features"))
        
        if hasattr(self, 'feature_labels'):
            feature_data_keys = [
                ("intro_feature1_icon", "intro_feature1_text"),
                ("intro_feature2_icon", "intro_feature2_text"),
                ("intro_feature3_icon", "intro_feature3_text"),
                ("intro_feature4_icon", "intro_feature4_text"),
                ("intro_feature5_icon", "intro_feature5_text"),
            ]
            default_feature_texts = [
                ("✨", "Automated Compliance Checks: Identify potential compliance gaps and risks quickly."),
                ("📚", "Regulatory Summarization: Condense lengthy documents into concise summaries."),
                ("🔍", "Semantic Search & Q&A: Find specific information and get answers about regulations."),
                ("🛡️", "Data Security & Privacy: Your documents are processed locally, ensuring confidentiality."),
                ("⚙️", "Customizable Analysis: Tailor the AI analysis to focus on specific regulatory aspects."),
            ]

            for i, label_pair in enumerate(self.feature_labels):
                icon_label, text_label = label_pair
                icon_key, text_key = feature_data_keys[i]
                default_icon, default_text = default_feature_texts[i]
                
                icon_label.setText(self.translator.get(icon_key, default_icon))
                text_label.setText(self.translator.get(text_key, default_text))

        # Remove Data Journey and Trust card updates as they are removed
            
        logger.debug("IntroPage UI retranslated")


    def _init_ui(self):
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(24)
        self.setLayout(main_layout)

        # Header Section
        header_section = self._create_header_section()
        main_layout.addLayout(header_section)

        # Core Info Section
        core_info_section = self._create_core_info_section()
        main_layout.addLayout(core_info_section)

        # CTA Section
        cta_section = self._create_cta_section()
        main_layout.addLayout(cta_section)
        
        main_layout.addStretch(1)  # Add stretch to push content to the top

    def _create_header_section(self):
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        self.title_label = QLabel(self.translator.get("intro_title", "<h1>Regulens-AI</h1>"))
        self.title_label.setObjectName("introPageTitleLabel") # Added object name
        self.title_label.setTextFormat(Qt.TextFormat.RichText)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.title_label)

        # Subtitle
        self.subtitle_label = QLabel(self.translator.get("intro_subtitle_v2", "Harness the power of AI to navigate, understand, and manage complex regulatory landscapes with unparalleled efficiency and precision."))
        self.subtitle_label.setObjectName("introPageSubtitleLabel") # Added object name
        self.subtitle_label.setTextFormat(Qt.TextFormat.RichText)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.subtitle_label)

        return header_layout

    def _create_core_info_section(self):
        core_info_layout = QHBoxLayout()
        core_info_layout.setSpacing(32)
        core_info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Left Column: Core Pipeline
        left_column_layout = QVBoxLayout()
        core_pipeline_section = self._create_core_pipeline_section() # Renamed method
        left_column_layout.addWidget(core_pipeline_section, alignment=Qt.AlignmentFlag.AlignTop)
        left_column_layout.addStretch(1) 
        core_info_layout.addLayout(left_column_layout, 2) # Adjusted stretch factor to 2 (approx 2/5)

        # Right Column: Key Features
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(24)
        key_features_section = self._create_key_features_section() 
        right_column_layout.addWidget(key_features_section, alignment=Qt.AlignmentFlag.AlignTop)
        right_column_layout.addStretch(1)
        core_info_layout.addLayout(right_column_layout, 3) # Adjusted stretch factor to 3 (approx 3/5)

        return core_info_layout

    def _create_core_pipeline_section(self): # Renamed from _create_pipeline_card
        card = QFrame()
        card.setObjectName("corePipelineCard") # Renamed object name
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setContentsMargins(0, 0, 0, 0)
        card.setMaximumWidth(400) # Retain max width or adjust as needed
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0) # Use stylesheet for padding
        card_layout.setSpacing(15)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Use new key for title, and rename label attribute
        self.core_pipeline_title_label = QLabel(self.translator.get("intro_core_pipeline_title", "Core Pipeline"))
        self.core_pipeline_title_label.setObjectName("corePipelineTitleLabel") # Added object name
        self.core_pipeline_title_label.setTextFormat(Qt.TextFormat.RichText) 
        self.core_pipeline_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # Removed inline stylesheet: "font-size: 18pt; font-weight: bold; margin-bottom: 10px;"

        card_layout.addWidget(self.core_pipeline_title_label)

        pipeline_steps_layout = QVBoxLayout()
        pipeline_steps_layout.setSpacing(12)

        self.pipeline_step_labels = [] # Retain this for retranslation (list of (icon_label, text_label) tuples)

        # Updated keys and default texts for steps
        steps_data_keys = [
            ("intro_pipeline_step1_title_v2", "intro_pipeline_step1_desc_v2"),
            ("intro_pipeline_step2_title_v2", "intro_pipeline_step2_desc_v2"),
            ("intro_pipeline_step3_title_v2", "intro_pipeline_step3_desc_v2"),
            ("intro_pipeline_step4_title_v2", "intro_pipeline_step4_desc_v2")
        ]
        default_steps_text = [ # Default texts should match the new content structure
            ("<strong>1. Secure Document Upload</strong>", "<small>Initiate the process by securely uploading your regulatory documents...</small>"),
            ("<strong>2. Intelligent AI Analysis</strong>", "<small>Leverage advanced AI algorithms for in-depth text extraction...</small>"),
            ("<strong>3. Actionable Insight Generation</strong>", "<small>Receive AI-powered summaries, extracted obligations...</small>"),
            ("<strong>4. Interactive Review & Export</strong>", "<small>Engage with the analyzed content through an intuitive interface...</small>")
        ]
        step_icons = ["📄", "⚙️", "🤖", "📝"] # Icons can remain the same or be updated

        for i in range(len(steps_data_keys)):
            icon_char = step_icons[i]
            title_key, desc_key = steps_data_keys[i]
            default_title, default_desc = default_steps_text[i]

            step_layout = QHBoxLayout()
            step_layout.setSpacing(12)
            step_layout.setAlignment(Qt.AlignmentFlag.AlignTop)


            step_icon_label = QLabel(icon_char)
            step_icon_label.setFixedWidth(30) # Icon width
            # Removed inline stylesheet: "font-size: 16pt;"

            # Get translated text without HTML tags for title if preferred, then format description
            translated_title = self.translator.get(title_key, default_title)
            translated_desc = self.translator.get(desc_key, default_desc)
            
            # Combine title and description, possibly with different styling
            # Using QLabel's rich text for simplicity here
            combined_text = f"<div style='font-weight:bold;'>{translated_title}</div><small>{translated_desc}</small>"
            step_text_label = QLabel(combined_text)
            step_text_label.setTextFormat(Qt.TextFormat.RichText)
            step_text_label.setWordWrap(True)
            step_text_label.setAlignment(Qt.AlignmentFlag.AlignTop)


            step_layout.addWidget(step_icon_label)
            step_layout.addWidget(step_text_label, 1) # Give text label more stretch factor
            pipeline_steps_layout.addLayout(step_layout)
            
            self.pipeline_step_labels.append((step_icon_label, step_text_label)) # Store for retranslation

            if i < len(steps_data_keys) - 1:
                arrow_label = QLabel("⬇️") 
                arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pipeline_steps_layout.addWidget(arrow_label)

        card_layout.addLayout(pipeline_steps_layout)
        card_layout.addStretch(1)
        card.setLayout(card_layout)
        return card

    def _create_key_features_section(self):
        card = QFrame()
        card.setObjectName("keyFeaturesCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setContentsMargins(0,0,0,0) # Use stylesheet for padding
        # card.setMaximumWidth(450) # Optional: set max width if needed

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0,0,0,0) # Use stylesheet for padding
        card_layout.setSpacing(15)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.key_features_title_label = QLabel(self.translator.get("intro_key_features_title", "Key Features"))
        self.key_features_title_label.setObjectName("keyFeaturesTitleLabel") # Added object name
        self.key_features_title_label.setTextFormat(Qt.TextFormat.RichText) 
        self.key_features_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # Removed inline stylesheet: "font-size: 18pt; font-weight: bold; margin-bottom: 10px;"
        card_layout.addWidget(self.key_features_title_label)

        features_layout = QVBoxLayout()
        features_layout.setSpacing(12)
        
        self.feature_labels = [] # List of (icon_label, text_label)

        feature_data = [
            ("intro_feature1_icon", "intro_feature1_text", "✨", "Automated Compliance Checks..."),
            ("intro_feature2_icon", "intro_feature2_text", "📚", "Regulatory Summarization..."),
            ("intro_feature3_icon", "intro_feature3_text", "🔍", "Semantic Search & Q&A..."),
            ("intro_feature4_icon", "intro_feature4_text", "🛡️", "Data Security & Privacy..."),
            ("intro_feature5_icon", "intro_feature5_text", "⚙️", "Customizable Analysis..."),
        ]

        for icon_key, text_key, default_icon, default_text in feature_data:
            feature_item_layout = QHBoxLayout()
            feature_item_layout.setSpacing(10)
            feature_item_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            icon_label = QLabel(self.translator.get(icon_key, default_icon))
            icon_label.setFixedWidth(30) # Adjust as needed
            # Removed inline stylesheet: "font-size: 16pt;"

            text_label = QLabel(self.translator.get(text_key, default_text))
            text_label.setWordWrap(True)
            text_label.setTextFormat(Qt.TextFormat.RichText) # Allow rich text for feature descriptions
            text_label.setAlignment(Qt.AlignmentFlag.AlignTop)


            feature_item_layout.addWidget(icon_label)
            feature_item_layout.addWidget(text_label, 1) # Text takes available space
            features_layout.addLayout(feature_item_layout)
            self.feature_labels.append((icon_label, text_label))

        card_layout.addLayout(features_layout)
        card_layout.addStretch(1)
        card.setLayout(card_layout)
        return card

    def _create_cta_section(self):
        cta_layout = QVBoxLayout()
        cta_layout.setContentsMargins(0, 40, 0, 0)
        cta_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.get_started_button = QPushButton(self.translator.get("intro_get_started_button", "Get Started"))
        self.get_started_button.setObjectName("getStartedButton")
        self.get_started_button.setFixedSize(220, 50)
        self.get_started_button.clicked.connect(self.start_requested.emit)
        
        button_container_layout = QHBoxLayout()
        button_container_layout.addStretch()
        button_container_layout.addWidget(self.get_started_button)
        button_container_layout.addStretch()
        
        cta_layout.addLayout(button_container_layout)
        return cta_layout


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = QWidget()
    main_window.setWindowTitle("Regulens-AI Introduction (PySide6)")
    main_window.setGeometry(100, 100, 1200, 900)

    # Dummy translator for standalone execution
    class DummyTranslator:
        def get(self, key, default_text=""): return default_text
        def current_lang_code(self): return "en"
        language_changed = Signal() # Dummy signal

    translator_instance = DummyTranslator()
    intro_page = IntroPage(translator_instance)
    
    def on_start_requested():
        print("Get Started button clicked! (PySide6) Transitioning to next page...")
        intro_page.hide()

    intro_page.start_requested.connect(on_start_requested)

    layout = QVBoxLayout(main_window)
    layout.addWidget(intro_page)
    main_window.setLayout(layout)
    main_window.show()
    
    sys.exit(app.exec())
