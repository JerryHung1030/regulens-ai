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

    def compare(self, project_id: str, input_path: Path, ref_path: Path, **scenario_params: Any) -> CompareResponse:
        logger.info("Comparing %s to %s for project %s", input_path, ref_path, project_id)
        input_doc_content = self.load_json(input_path)
        ref_doc_content = self.load_json(ref_path)
        try:
            resp = self.api_client.compare(project_id, input_doc_content, ref_doc_content, **scenario_params)
        except Exception as exc:
            logger.error("Comparison failed: %s", exc)
            raise CompareError(str(exc)) from exc
        logger.info("Comparison succeeded")
        return resp

    async def acompare(self, project_id: str, input_path: Path, ref_path: Path, **scenario_params: Any) -> CompareResponse:
        """Asynchronous wrapper around :meth:`ApiClient.acompare`."""
        input_doc_content = self.load_json(input_path)
        ref_doc_content = self.load_json(ref_path)
        logger.info("Comparing %s to %s for project %s (async)", input_path, ref_path, project_id)
        try:
            resp = await self.api_client.acompare(project_id, input_doc_content, ref_doc_content, **scenario_params)
        except Exception as exc:
            logger.error("Async comparison failed: %s", exc)
            raise CompareError(str(exc)) from exc
        logger.info("Async comparison succeeded")
        return resp
