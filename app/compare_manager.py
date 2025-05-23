from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .api_client import ApiClient, CompareResponse


class CompareError(Exception):
    pass


class CompareManager:
    """Handle document loading and comparison.

    Exposes both synchronous :meth:`compare` and asynchronous
    :meth:`acompare` helpers.
    """

    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    def load_json(self, path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - simple error wrap
            raise CompareError(str(exc)) from exc

    def compare(self, input_path: Path, ref_path: Path, **params: Any) -> CompareResponse:
        input_doc = self.load_json(input_path)
        ref_doc = self.load_json(ref_path)
        try:
            return self.api_client.compare(input_doc, ref_doc, **params)
        except Exception as exc:
            raise CompareError(str(exc)) from exc

    async def acompare(self, input_path: Path, ref_path: Path, **params: Any) -> CompareResponse:
        """Asynchronous wrapper around :meth:`ApiClient.acompare`."""
        input_doc = self.load_json(input_path)
        ref_doc = self.load_json(ref_path)
        try:
            return await self.api_client.acompare(input_doc, ref_doc, **params)
        except Exception as exc:
            raise CompareError(str(exc)) from exc
