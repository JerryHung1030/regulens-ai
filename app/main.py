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


# def _load_config(path: Path) -> dict:
#     """Load configuration from YAML without requiring PyYAML."""
#     text = path.read_text()
#     if yaml is not None:
#         return yaml.safe_load(text)
#     data: dict[str, str] = {}
#     for line in text.splitlines():
#         line = line.strip()
#         if not line or line.startswith("#"):
#             continue
#         if ":" in line:
#             k, v = line.split(":", 1)
#             data[k.strip()] = v.strip().strip('"')
#     return data


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
        css_file_path = Path(__file__).parent / "assets" / "dark.css"
        logger.info(f"Attempting to load CSS from: {css_file_path}")
        if css_file_path.exists():
            with open(css_file_path, "r", encoding="utf-8") as f:
                css_content = f.read()
                qapp.setStyleSheet(css_content)
                logger.info("Dark theme CSS applied successfully.")
        else:
            logger.warning(f"Dark theme CSS file not found: {css_file_path}")
    # Add logic for other themes here if needed

    # MainWindow no longer takes CompareManager
    main_window = MainWindow(settings)
    main_window.resize(1100, 720)
    main_window.show()

    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
