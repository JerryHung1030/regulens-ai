"""Entry point for the Regulens-AI application.

This provides a minimal command-line interface that mirrors a subset of the
planned GUI workflow. It loads API settings from ``config_default.yaml`` and
outputs the raw Markdown diff to ``stdout`` or a file.
"""

import sys
try:  # optional dependency
    import yaml
except Exception:  # pragma: no cover - fallback for minimal environments
    yaml = None  # type: ignore

from .logger import logger
# Import GUI components
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from .mainwindow import MainWindow
from .settings import Settings
from pathlib import Path

def main(argv: list[str] | None = None) -> None:
    # CLI argument parsing can be added here if needed for GUI configuration
    # For now, we directly launch the GUI.
    logger.info("Application starting...")

    qapp = QApplication(sys.argv if argv is None else [sys.argv[0]] + argv)
    # 設定支援中文的字體
    font = QFont()
    font.setFamily("WenQuanYi Zen Hei") # 或者尝试其他支援中文的字體，如 "Noto Sans CJK SC"
    qapp.setFont(font)

    settings = Settings()  # Load settings (e.g., from config_default.yaml or user settings)

    # Load and apply theme CSS
    theme_name = settings.get("theme", "default")
    logger.info(f"Loaded theme setting: {theme_name}")

    if theme_name == "dark":
        css_file_path = Path(__file__).parent.parent / "assets" / "dark_theme.qss"
        logger.info(f"Attempting to load CSS from: {css_file_path}")
        if css_file_path.exists():
            with open(css_file_path, "r", encoding="utf-8") as f:
                css_content = f.read()
                qapp.setStyleSheet(css_content)
                logger.info("Dark theme CSS applied successfully.")
        else:
            logger.warning(f"Dark theme CSS file not found: {css_file_path}")
    elif theme_name == "light":
        css_file_path = Path(__file__).parent.parent / "assets" / "light_theme.qss"
        logger.info(f"Attempting to load CSS from: {css_file_path}")
        if css_file_path.exists():
            with open(css_file_path, "r", encoding="utf-8") as f:
                css_content = f.read()
                qapp.setStyleSheet(css_content)
                logger.info("Light theme CSS applied successfully.")
        else:
            logger.warning(f"Light theme CSS file not found: {css_file_path}")
    elif theme_name == "system":
        # 檢測系統主題
        is_dark_mode = qapp.styleHints().colorScheme() == Qt.ColorScheme.Dark
        theme_file = "dark_theme.qss" if is_dark_mode else "light_theme.qss"
        css_file_path = Path(__file__).parent.parent / "assets" / theme_file
        logger.info(f"Attempting to load system theme CSS from: {css_file_path}")
        if css_file_path.exists():
            with open(css_file_path, "r", encoding="utf-8") as f:
                css_content = f.read()
                qapp.setStyleSheet(css_content)
                logger.info(f"System theme CSS ({theme_file}) applied successfully.")
        else:
            logger.warning(f"System theme CSS file not found: {css_file_path}")

    # MainWindow no longer takes CompareManager
    main_window = MainWindow(settings)
    main_window.resize(1100, 720)
    main_window.show()

    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
