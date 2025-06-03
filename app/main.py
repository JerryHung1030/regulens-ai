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
from .mainwindow import MainWindow
from .settings import Settings


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
    settings = Settings()  # Load settings (e.g., from config_default.yaml or user settings)

    # MainWindow no longer takes CompareManager
    main_window = MainWindow(settings)
    main_window.resize(1100, 720)
    main_window.show()

    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
