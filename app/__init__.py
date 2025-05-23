"""Regulens-AI application package."""

try:  # optional dependency for tests
    from .ui_main import MainWindow
    from .config_dialog import ConfigDialog
except Exception:  # pragma: no cover - optional GUI
    MainWindow = None  # type: ignore
    ConfigDialog = None  # type: ignore

__all__ = ["MainWindow", "ConfigDialog"]
