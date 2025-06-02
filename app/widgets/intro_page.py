# app/widgets/intro_page.py

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal  # 直接從 QtCore 導入 Signal
# from PySide6.QtGui import QPixmap


class IntroPage(QWidget):
    start_requested = Signal()  # 使用直接導入的 Signal

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        root_layout.setSpacing(24)
        root_layout.setContentsMargins(40, 40, 40, 40)

        # 1. 標題區
        title = QLabel(
            "<h1>Regulens-AI</h1>"
            "<p style='font-size:16px; color:#1565c0;'>「合規文件比對，一鍵產出審計報告」</p>"
        )
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        root_layout.addWidget(title)

        # 2. Pipeline Flow 卡片
        pipeline_card = QFrame()
        pipeline_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pipeline_layout = QHBoxLayout(pipeline_card)
        pipeline_layout.setSpacing(16)
        pipeline_layout.setContentsMargins(16, 16, 16, 16)

        steps = [
            ("📄 Controls", "政策文字"),
            ("↦", ""),
            ("📄 Procedures", "執行程序"),
            ("↦", ""),
            ("📄 Evidence", "佐證檔案"),
            ("↦", ""),
            ("⚙ 正規化", ""),
            ("⚙ 向量化", ""),
            ("⚙ 建立索引", ""),
            ("🤖 LLM 評估", ""),
            ("📝 生成報告", ""),
        ]
        for label_text, sub_text in steps:
            lbl = QLabel(f"<b>{label_text}</b><br><small>{sub_text}</small>")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            pipeline_layout.addWidget(lbl)

        root_layout.addWidget(pipeline_card)

        # 3. Data Journey 卡片
        data_card = QFrame()
        data_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        data_layout = QVBoxLayout(data_card)
        data_layout.setSpacing(8)
        data_layout.setContentsMargins(16, 16, 16, 16)

        data_title = QLabel("<b>Data Journey（資料流分段）</b>")
        data_title.setAlignment(Qt.AlignLeft)
        data_layout.addWidget(data_title)

        data_list = QLabel(
            "<ul>"
            "<li>Ingestion  ─  支援 <b>TXT</b> / <b>PDF</b> / <b>CSV</b></li>"
            "<li>Embedding  ─  OpenAI <b>text-embedding-3-large</b></li>"
            "<li>Retrieval  ─  FAISS <b>k-NN</b> 相似度搜尋</li>"
            "<li>Assessment ─  GPT-4o 產生 <b>Pass</b> / <b>Partial</b> / …</li>"
            "<li>Report     ─  Markdown → (選擇性 PDF)</li>"
            "</ul>"
        )
        data_list.setTextFormat(Qt.RichText)
        data_list.setWordWrap(True)
        data_list.setAlignment(Qt.AlignLeft)
        data_list.setMaximumWidth(720)
        data_layout.addWidget(data_list)

        root_layout.addWidget(data_card)

        # 4. Why Trust It? 卡片
        trust_card = QFrame()
        trust_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        trust_layout = QVBoxLayout(trust_card)
        trust_layout.setSpacing(8)
        trust_layout.setContentsMargins(16, 16, 16, 16)

        trust_title = QLabel("<b>Why Trust It? ⭐</b>")
        trust_title.setAlignment(Qt.AlignLeft)
        trust_layout.addWidget(trust_title)

        trust_list = QLabel(
            "<ul>"
            "<li>單檔 Pipeline，可離線重跑</li>"
            "<li>嚴格快取：內容雜湊 + 向量索引</li>"
            "<li>全流程可追蹤（logs/ & output/）</li>"
            "</ul>"
        )
        trust_list.setTextFormat(Qt.RichText)
        trust_list.setWordWrap(True)
        trust_list.setAlignment(Qt.AlignLeft)
        trust_list.setMaximumWidth(720)
        trust_layout.addWidget(trust_list)

        root_layout.addWidget(trust_card)

        # 5. Get Started 按鈕
        btn_start = QPushButton("Get Started")
        btn_start.setFixedSize(180, 44)
        btn_start.clicked.connect(lambda: self.start_requested.emit())
        root_layout.addWidget(btn_start, alignment=Qt.AlignCenter)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: #fafafa;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            """
        )
