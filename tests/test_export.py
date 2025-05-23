from pathlib import Path

import pytest

pytest.importorskip('weasyprint')
from PyPDF2 import PdfReader

from app.export import to_pdf, to_txt


def test_to_txt(tmp_path):
    path = tmp_path / 'out.txt'
    to_txt('hello', path)
    assert path.read_text() == 'hello'


def test_to_pdf(tmp_path):
    pdf_path = tmp_path / 'out.pdf'
    to_pdf('# Title', pdf_path)
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 1
