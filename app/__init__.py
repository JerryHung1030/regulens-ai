"""Regulens-AI application package."""

try:  # optional dependency for tests
    from .ui_main import MainWindow
except Exception:  # pragma: no cover - optional GUI
    MainWindow = None  # type: ignore

__all__ = ["MainWindow"]
