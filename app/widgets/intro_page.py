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
            self.subtitle_label.setText(self.translator.get("intro_subtitle", "<p style='margin:0px;'>Compliance document comparison, one-click audit report generation</p>"))
        
        # Update pipeline card title
        if hasattr(self, 'pipeline_card_title_label'):
            self.pipeline_card_title_label.setText(self.translator.get("intro_workflow_title", "<h2>Workflow</h2>"))

        # Update Get Started button
        if hasattr(self, 'get_started_button'):
            self.get_started_button.setText(self.translator.get("intro_get_started_button", "Get Started"))

        # TODO: Add more elements here, like pipeline steps, data journey, trust card texts
        # For now, log that other parts would be updated
        logger.debug("IntroPage retranslated (partially). More elements pending full refactor.")

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
        title_label = QLabel("<h1>Regulens-AI</h1>")
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)

        # Subtitle
        self.subtitle_label = QLabel(self.translator.get("intro_subtitle", "<p style='margin:0px;'>合規文件比對，一鍵產出審計報告</p>"))
        self.subtitle_label.setTextFormat(Qt.TextFormat.RichText)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.subtitle_label)

        return header_layout

    def _create_core_info_section(self):
        core_info_layout = QHBoxLayout()
        core_info_layout.setSpacing(32)  # 保持之前的左右間距
        core_info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Left Column
        left_column_layout = QVBoxLayout()
        pipeline_card = self._create_pipeline_card()
        left_column_layout.addWidget(pipeline_card, alignment=Qt.AlignmentFlag.AlignTop)
        left_column_layout.addStretch(1)
        # 左邊欄寬度較小：stretch factor = 1
        core_info_layout.addLayout(left_column_layout, 1)

        # Right Column
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(24)  # 保持之前的卡片間距
        data_journey_card = self._create_data_journey_card()
        trust_card = self._create_trust_card()
        right_column_layout.addWidget(data_journey_card, alignment=Qt.AlignmentFlag.AlignTop)
        right_column_layout.addWidget(trust_card, alignment=Qt.AlignmentFlag.AlignTop)
        right_column_layout.addStretch(1)
        # 右邊欄寬度較大：stretch factor = 2
        core_info_layout.addLayout(right_column_layout, 1)

        return core_info_layout

    def _create_pipeline_card(self):
        card = QFrame()
        card.setObjectName("pipelineCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        # 清除 QFrame 預設 margins，改由 stylesheet 控制 padding
        card.setContentsMargins(0, 0, 0, 0)
        # 限制左邊卡片最大寬度
        card.setMaximumWidth(400)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(15)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.pipeline_card_title_label = QLabel(self.translator.get("intro_workflow_title", "<h2>工作流程</h2>"))
        self.pipeline_card_title_label.setTextFormat(Qt.TextFormat.RichText)
        self.pipeline_card_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(self.pipeline_card_title_label)

        workflow_steps_layout = QVBoxLayout()
        workflow_steps_layout.setSpacing(12)  # 微調步驟間距

        steps_data = [
            ("📄", "<strong>Controls, Procedures, Evidence</strong><br><small>Upload your compliance documents</small>"),
            ("⚙️", "<strong>Processing</strong><br><small>Normalization, Vectorization, Indexing</small>"),
            ("🤖", "<strong>LLM Assessment</strong><br><small>AI-powered evaluation</small>"),
            ("📝", "<strong>Audit Report</strong><br><small>Markdown & PDF output</small>")
        ]

        for i, (icon, text) in enumerate(steps_data):
            step_layout = QHBoxLayout()
            step_layout.setSpacing(12)

            step_icon_label = QLabel(icon)
            step_icon_label.setFixedWidth(30)

            step_text_label = QLabel(text)
            step_text_label.setTextFormat(Qt.TextFormat.RichText)
            step_text_label.setWordWrap(True)

            step_layout.addWidget(step_icon_label)
            step_layout.addWidget(step_text_label)
            workflow_steps_layout.addLayout(step_layout)

            if i < len(steps_data) - 1:
                arrow_label = QLabel("⬇️")
                arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                workflow_steps_layout.addWidget(arrow_label)

        card_layout.addLayout(workflow_steps_layout)
        card_layout.addStretch(1)
        card.setLayout(card_layout)
        return card

    def _create_data_journey_card(self):
        card = QFrame()
        card.setObjectName("dataJourneyCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setContentsMargins(0, 0, 0, 0)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        card_layout.setSpacing(15)

        title = QLabel("<h3>資料流程 (Data Journey)</h3>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(title)

        list_data_text = """
        <ul style='list-style-type: none; padding: 0; margin: 0;'>
          <li style='margin-bottom: 8px;'><strong>Ingestion：</strong>支援 TXT(PDF/CSV TBC)</li>
          <li style='margin-bottom: 8px;'><strong>Embedding：</strong>OpenAI text-embedding-3-large</li>
          <li style='margin-bottom: 8px;'><strong>Retrieval：</strong>FAISS k-NN similarity search</li>
          <li style='margin-bottom: 8px;'><strong>Assessment：</strong>GPT-4o for Pass / Partial / Fail</li>
          <li style='margin-bottom: 8px;'><strong>Report：</strong>Markdown → Optional PDF</li>
        </ul>
        """
        list_data_label = QLabel(list_data_text)
        list_data_label.setTextFormat(Qt.TextFormat.RichText)
        list_data_label.setWordWrap(True)
        # 卡片內文列表由 14pt → 12pt
        card_layout.addWidget(list_data_label)
        card_layout.addStretch(1)
        card.setLayout(card_layout)
        return card

    def _create_trust_card(self):
        card = QFrame()
        card.setObjectName("trustCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setContentsMargins(0, 0, 0, 0)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        card_layout.setSpacing(15)

        title = QLabel("<h3>為什麼信任 Regulens-AI？</h3>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(title)

        list_trust_text = """
        <ul style='list-style-type: none; padding: 0; margin: 0;'>
          <li style='margin-bottom: 8px;'>✅ <strong>Offline Capability：</strong>支援pipeline並可離線執行。</li>
          <li style='margin-bottom: 8px;'>🔒 <strong>Robust Caching：</strong>Content hashing 與 vector indexing。</li>
          <li style='margin-bottom: 8px;'>🔍 <strong>Full Traceability：</strong>logs/ 與 output/ 中的詳細日誌。</li>
        </ul>
        """
        list_trust_label = QLabel(list_trust_text)
        list_trust_label.setTextFormat(Qt.TextFormat.RichText)
        list_trust_label.setWordWrap(True)
        card_layout.addWidget(list_trust_label)
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
