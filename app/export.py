from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt

try:  # optional dependency
    import weasyprint
except Exception:  # pragma: no cover - environment lacking package
    weasyprint = None


def to_txt(markdown_str: str, path: Path) -> None:
    path.write_text(markdown_str, encoding="utf-8")


def to_pdf(markdown_str: str, path: Path) -> None:
    if weasyprint is None:
        raise RuntimeError("weasyprint is not available")
    html = MarkdownIt("commonmark", {"html": True}).render(markdown_str)
    weasyprint.HTML(string=html).write_pdf(str(path))
