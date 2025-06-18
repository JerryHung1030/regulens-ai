import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy
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
            self.subtitle_label.setText(self.translator.get("intro_slogan", "Default Slogan"))
        
        # Update core pipeline section title (renamed from pipeline_card_title_label)
        if hasattr(self, 'core_pipeline_title_label'): # Renamed attribute
            self.core_pipeline_title_label.setText(self.translator.get("intro_core_pipeline_title", "Core Process Flow"))

        # Update Get Started button
        if hasattr(self, 'get_started_button'):
            self.get_started_button.setText(self.translator.get("intro_get_started_button", "Get Started"))

        # Update Header Section
        if hasattr(self, 'title_label'):
            self.title_label.setText(self.translator.get("intro_title", "<h1>Regulens-AI</h1>")) # intro_title is still the same

        # Update Core Pipeline Section (previously Pipeline Card)
        # self.core_pipeline_title_label is already updated above
        if hasattr(self, 'pipeline_step_labels'):
            steps_data_keys = [
                ("intro_process_step_A_title", "intro_process_step_A_desc"),
                ("intro_process_step_B_title", "intro_process_step_B_desc"),
                ("intro_process_step_C_title", "intro_process_step_C_desc"),
                ("intro_process_step_D_title", "intro_process_step_D_desc"),
            ]
            default_steps_text = [
                ("<strong>Step A Title</strong>", "<small>Step A Description</small>"),
                ("<strong>Step B Title</strong>", "<small>Step B Description</small>"),
                ("<strong>Step C Title</strong>", "<small>Step C Description</small>"),
                ("<strong>Step D Title</strong>", "<small>Step D Description</small>"),
            ]
            for i, label_pair in enumerate(self.pipeline_step_labels):
                icon_label, text_label = label_pair # Assuming structure (icon_label, text_label)
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

        # Update How to Use Section Title (used in top section)
        if hasattr(self, 'how_to_use_title_label'): # This label is part of _create_how_to_use_top_section
            self.how_to_use_title_label.setText(self.translator.get("intro_how_to_use_title", "4 Steps to Use"))

        # Update How to Use Step Titles (the small boxes in the top section)
        if hasattr(self, 'how_to_use_step_title_labels'):
            htu_steps_title_keys = [
                "intro_how_to_use_step1_title",
                "intro_how_to_use_step2_title",
                "intro_how_to_use_step3_title",
                "intro_how_to_use_step4_title",
            ]
            default_htu_steps_titles = [
                "1. Upload", "2. Analyze", "3. Review", "4. Act"
            ]
            for i, label in enumerate(self.how_to_use_step_title_labels):
                label.setText(self.translator.get(htu_steps_title_keys[i], default_htu_steps_titles[i]))
            
        logger.debug("IntroPage UI retranslated")


    def _init_ui(self):
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        main_layout.setContentsMargins(40, 20, 40, 40)  # 減少上方間距從 40 改為 20
        main_layout.setSpacing(15)  # 減少間距從 20 改為 15
        self.setLayout(main_layout)

        # Header Section (Title + Slogan)
        header_section = self._create_header_section()
        main_layout.addLayout(header_section)

        # NEW LAYOUT: Top Section (How to Use Titles)
        how_to_use_top_section = self._create_how_to_use_top_section()
        main_layout.addWidget(how_to_use_top_section)

        # NEW LAYOUT: Bottom Section (Core Pipeline + Key Features)
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        core_pipeline_bl_section = self._create_core_pipeline_bottom_left_section()
        core_pipeline_bl_section.setMinimumHeight(400)  # 增加最小高度
        bottom_layout.addWidget(core_pipeline_bl_section, 1)

        key_features_br_section = self._create_key_features_bottom_right_section()
        key_features_br_section.setMinimumHeight(400)  # 增加最小高度
        bottom_layout.addWidget(key_features_br_section, 1)
        
        main_layout.addLayout(bottom_layout)

        # CTA Section (Get Started Button)
        cta_section = self._create_cta_section()
        main_layout.addLayout(cta_section)
        
        main_layout.addStretch(1)

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
        self.subtitle_label = QLabel(self.translator.get("intro_slogan", "Default Slogan"))
        self.subtitle_label.setObjectName("introPageSubtitleLabel") # Added object name
        self.subtitle_label.setTextFormat(Qt.TextFormat.RichText)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.subtitle_label)

        return header_layout

    # This method is removed as its logic is now in _init_ui's bottom_layout
    # def _create_core_info_section(self):
    #     pass 

    def _create_core_pipeline_bottom_left_section(self): 
        card = QFrame()
        card.setObjectName("corePipelineBottomCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setFrameShadow(QFrame.Shadow.Raised)
        # card.setContentsMargins(0, 0, 0, 0) # Margins are now set on the layout
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10) # Consistent card padding
        card_layout.setSpacing(8) # Adjusted main card spacing
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.core_pipeline_title_label = QLabel(self.translator.get("intro_core_pipeline_title", "Core Process Flow"))
        self.core_pipeline_title_label.setObjectName("corePipelineTitleLabel")
        self.core_pipeline_title_label.setTextFormat(Qt.TextFormat.RichText) 
        self.core_pipeline_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(self.core_pipeline_title_label)

        pipeline_steps_layout = QVBoxLayout()
        pipeline_steps_layout.setSpacing(18) # Adjusted spacing for steps

        self.pipeline_step_labels = [] 

        steps_data = [
            ("intro_process_step_A_title", "intro_process_step_A_desc"),
            ("intro_process_step_B_title", "intro_process_step_B_desc"),
            ("intro_process_step_C_title", "intro_process_step_C_desc"),
            ("intro_process_step_D_title", "intro_process_step_D_desc"),
        ]
        default_steps_text = [
            ("<strong>Step A Title</strong>", "<small>Step A Description</small>"),
            ("<strong>Step B Title</strong>", "<small>Step B Description</small>"),
            ("<strong>Step C Title</strong>", "<small>Step C Description</small>"),
            ("<strong>Step D Title</strong>", "<small>Step D Description</small>"),
        ]
        step_icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]

        for i in range(len(steps_data)):
            icon_char = step_icons[i]
            title_key, desc_key = steps_data[i]
            default_title, default_desc = default_steps_text[i]

            step_layout = QHBoxLayout()
            step_layout.setSpacing(12)
            step_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            step_icon_label = QLabel(icon_char)
            step_icon_label.setMinimumWidth(30) # Ensure icon width
            step_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center icon

            translated_title = self.translator.get(title_key, default_title)
            translated_desc = self.translator.get(desc_key, default_desc)
            
            combined_text = f"{translated_title}<br>{translated_desc}" # Keep title bold via default text
            step_text_label = QLabel(combined_text)
            step_text_label.setTextFormat(Qt.TextFormat.RichText)
            step_text_label.setWordWrap(True)
            step_text_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding) # Allow vertical expansion
            # step_text_label.setAlignment(Qt.AlignmentFlag.AlignTop) # Default alignment should be fine

            step_layout.addWidget(step_icon_label)
            step_layout.addWidget(step_text_label, 1)
            pipeline_steps_layout.addLayout(step_layout)
            
            self.pipeline_step_labels.append((step_icon_label, step_text_label))

            if i < len(steps_data) - 1: # No arrow for the last item
                # If you want arrows between steps, add them here.
                # For this version, we'll omit the arrows between A, B, C, D steps
                # to simplify and differentiate from the previous design.
                pass


        card_layout.addLayout(pipeline_steps_layout)
        card_layout.addStretch(1)
        card.setLayout(card_layout)
        return card

    def _create_key_features_bottom_right_section(self):
        card = QFrame()
        card.setObjectName("keyFeaturesBottomCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setFrameShadow(QFrame.Shadow.Raised)
        # card.setContentsMargins(0,0,0,0) # Margins are now set on the layout

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10) # Consistent card padding
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
            icon_label.setMinimumWidth(30) # Ensure icon width
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center icon

            text_label = QLabel(self.translator.get(text_key, default_text))
            text_label.setWordWrap(True)
            text_label.setTextFormat(Qt.TextFormat.RichText) # Allow rich text for feature descriptions
            text_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding) # Allow vertical expansion
            # text_label.setAlignment(Qt.AlignmentFlag.AlignTop) # Default alignment should be fine


            feature_item_layout.addWidget(icon_label)
            feature_item_layout.addWidget(text_label, 1) # Text takes available space
            features_layout.addLayout(feature_item_layout)
            self.feature_labels.append((icon_label, text_label))

        card_layout.addLayout(features_layout)
        card_layout.addStretch(1)
        card.setLayout(card_layout)
        return card

    def _create_how_to_use_top_section(self):
        top_card = QFrame()
        top_card.setObjectName("howToUseTopCard")
        top_card.setFrameShape(QFrame.Shape.StyledPanel) # Ensure it can be styled by QFrame rules
        top_card.setFrameShadow(QFrame.Shadow.Raised) # Keep consistent shadow
        # top_card.setContentsMargins(0,0,0,0)

        top_card_layout = QVBoxLayout(top_card)
        top_card_layout.setContentsMargins(10, 10, 10, 10) # Consistent card padding
        top_card_layout.setSpacing(10) # Spacing between title and step boxes
        top_card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # This title label is now part of this top card
        self.how_to_use_title_label = QLabel(self.translator.get("intro_how_to_use_title", "How to Use"))
        self.how_to_use_title_label.setObjectName("howToUseTitleLabel")
        self.how_to_use_title_label.setTextFormat(Qt.TextFormat.RichText) 
        self.how_to_use_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        top_card_layout.addWidget(self.how_to_use_title_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # Title for Core Pipeline
        self.core_pipeline_title_label = QLabel(self.translator.get("intro_core_pipeline_title", "Core Process Flow"))
        self.core_pipeline_title_label.setObjectName("corePipelineTitleLabel")
        self.core_pipeline_title_label.setTextFormat(Qt.TextFormat.RichText)
        self.core_pipeline_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Title for Key Features
        self.key_features_title_label = QLabel(self.translator.get("intro_key_features_title", "Key Features"))
        self.key_features_title_label.setObjectName("keyFeaturesTitleLabel")
        self.key_features_title_label.setTextFormat(Qt.TextFormat.RichText)
        self.key_features_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        htu_steps_title_layout = QHBoxLayout() # Titles will be in a horizontal row
        htu_steps_title_layout.setSpacing(15) # Spacing between the title boxes

        self.how_to_use_step_title_labels = [] # Store these new labels

        htu_steps_title_keys = [
            "intro_how_to_use_step1_title",
            "intro_how_to_use_step2_title",
            "intro_how_to_use_step3_title",
            "intro_how_to_use_step4_title",
        ]
        default_htu_steps_titles = [
             "1. Upload Docs", "2. Initiate Analysis", "3. Review Insights", "4. Export & Act" # Shortened for boxes
        ]
        
        for i in range(len(htu_steps_title_keys)):
            title_key = htu_steps_title_keys[i]
            default_title = default_htu_steps_titles[i]
            
            step_title_label = QLabel(self.translator.get(title_key, default_title))
            step_title_label.setObjectName(f"htuStepTitleLabel{i+1}")
            step_title_label.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
            step_title_label.setWordWrap(True)
            step_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_title_label.setMinimumHeight(50)
            # step_title_label.setStyleSheet("padding: 5px; background-color: #f0f0f0;") # Removed inline style
            step_title_label.setProperty("class", "howToUseStepBox") # Added class for QSS

            htu_steps_title_layout.addWidget(step_title_label, 1) # Equal stretch
            self.how_to_use_step_title_labels.append(step_title_label)

        top_card_layout.addLayout(htu_steps_title_layout)
        top_card.setLayout(top_card_layout)
        return top_card

    def _create_cta_section(self):
        cta_layout = QVBoxLayout()
        cta_layout.setContentsMargins(0, 20, 0, 0)  # 減少上方間距從 40 改為 20
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
