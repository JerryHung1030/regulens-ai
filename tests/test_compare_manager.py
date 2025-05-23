import sys
from types import SimpleNamespace

sys.modules.setdefault('loguru', SimpleNamespace(logger=SimpleNamespace(add=lambda *a, **k: None)))

import pytest

from app.compare_manager import CompareManager, CompareError
from app.api_client import ApiClient


def test_load_json_invalid(tmp_path):
    bad = tmp_path / 'bad.json'
    bad.write_text('{broken}', encoding='utf-8')
    manager = CompareManager(ApiClient('http://x', 'k'))
    with pytest.raises(CompareError):
        manager.load_json(bad)


def test_load_json_missing(tmp_path):
    missing = tmp_path / 'missing.json'
    manager = CompareManager(ApiClient('http://x', 'k'))
    with pytest.raises(CompareError):
        manager.load_json(missing)
