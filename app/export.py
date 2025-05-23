from __future__ import annotations

from pathlib import Path
from importlib import resources

from markdown_it import MarkdownIt

from .logger import logger

try:  # optional dependency
    import weasyprint
except Exception:  # pragma: no cover - environment lacking package
    weasyprint = None


def to_txt(markdown_str: str, path: Path) -> None:
    path.write_text(markdown_str, encoding="utf-8")
    logger.info("Exported text to %s", path)


def to_pdf(markdown_str: str, path: Path) -> None:
    if weasyprint is None:
        logger.error("weasyprint is not available")
        raise RuntimeError("weasyprint is not available")
    html = MarkdownIt("commonmark", {"html": True}).render(markdown_str)
    css = _read_css()
    html_full = f"<style>{css}</style>{html}"
    weasyprint.HTML(string=html_full).write_pdf(str(path))
    logger.info("Exported PDF to %s", path)


def _read_css() -> str:
    """Return built-in PDF stylesheet."""
    try:
        with resources.files("assets").joinpath("pdf.css").open("r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""
