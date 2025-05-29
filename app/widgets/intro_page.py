from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class IntroPage(QWidget):
    start_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("<h1>Regulens-AI</h1><p>快速、可靠地比較內外規</p>")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        button_layout = QHBoxLayout()

        btn_start = QPushButton("Get Started")
        btn_start.setFixedHeight(38)
        btn_start.setStyleSheet("border-radius:19px; padding:0 24px;")
        btn_start.clicked.connect(self.start_requested.emit)
        button_layout.addWidget(btn_start)

        # btn_settings is removed
        # btn_settings.setFixedHeight(38)
        # btn_settings.setStyleSheet("border-radius:19px; padding:0 24px;")
        # btn_settings.clicked.connect(self.settings_requested.emit)
        # button_layout.addWidget(btn_settings)

        main_layout.addLayout(button_layout)
