from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .api_client import ApiClient, CompareResponse
from .logger import logger


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
        logger.info("Comparing %s to %s", input_path, ref_path)
        input_doc = self.load_json(input_path)
        ref_doc = self.load_json(ref_path)
        try:
            resp = self.api_client.compare(input_doc, ref_doc, **params)
        except Exception as exc:
            logger.error("Comparison failed: %s", exc)
            raise CompareError(str(exc)) from exc
        logger.info("Comparison succeeded")
        return resp

    async def acompare(self, input_path: Path, ref_path: Path, **params: Any) -> CompareResponse:
        """Asynchronous wrapper around :meth:`ApiClient.acompare`."""
        input_doc = self.load_json(input_path)
        ref_doc = self.load_json(ref_path)
        logger.info("Comparing %s to %s (async)", input_path, ref_path)
        try:
            resp = await self.api_client.acompare(input_doc, ref_doc, **params)
        except Exception as exc:
            logger.error("Async comparison failed: %s", exc)
            raise CompareError(str(exc)) from exc
        logger.info("Async comparison succeeded")
        return resp
