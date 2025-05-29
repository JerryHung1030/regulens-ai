"""Regulens-AI application package."""

try:
    from .mainwindow import MainWindow
except Exception:  # pragma: no cover - optional GUI
    MainWindow = None  # type: ignore

