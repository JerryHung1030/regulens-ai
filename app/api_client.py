from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import request

try:  # optional dependency for async HTTP
    import httpx  # type: ignore
except Exception:  # pragma: no cover - optional
    httpx = None


@dataclass
class CompareResponse:
    """Simple response model for API results."""
    result: str


class ApiClient:
    """
    HTTP client for the /api/v1/rag endpoint.
    Now the compare/acompare accept:
    compare(project_id, input_doc_content, ref_doc_content, **scenario_params).
    They will build the payload as RAGRequest schema demands:
    {
      "project_id": ...,
      "input_data": {...},
      "reference_data": {...},
      "scenario": { ...scenario_params... }
    }
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self._async_client: Optional["httpx.AsyncClient"] = None
        if httpx is not None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=timeout,
            )

    def compare(
        self,
        project_id: str,
        input_doc_content: Dict[str, Any],
        ref_doc_content: Dict[str, Any],
        **scenario_params: Any
    ) -> CompareResponse:
        """
        Synchronous comparison with urllib.
        Build a RAGRequest-like payload. Example:
        {
          "project_id": project_id,
          "input_data": {
              "level1": [
                   {
                     "sid": f"input_{project_id}",
                     "text": input_doc_content,
                     "metadata": { "project": project_id }
                   }
              ]
          },
          "reference_data": {
              "level1": [
                   {
                     "sid": f"ref_{project_id}",
                     "text": ref_doc_content,
                     "metadata": { "project": project_id }
                   }
              ]
          },
          "scenario": { ...scenario_params... }
        }
        POST /api/v1/rag
        """
        payload = {
            "project_id": project_id,
            "input_data": {
                "level1": [
                    {
                        "sid": f"input_{project_id}",
                        "text": input_doc_content,
                        "metadata": {"project": project_id}
                    }
                ]
            },
            "reference_data": {
                "level1": [
                    {
                        "sid": f"ref_{project_id}",
                        "text": ref_doc_content,
                        "metadata": {"project": project_id}
                    }
                ]
            },
            "scenario": scenario_params,
        }
        data = json.dumps(payload).encode("utf-8")
        req_url = f"{self.base_url}/api/v1/rag"
        req = request.Request(
            req_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=self.timeout) as resp:
            resp_data = resp.read()
        obj = json.loads(resp_data.decode("utf-8"))
        return CompareResponse(result=obj.get("result", ""))

    async def acompare(
        self,
        project_id: str,
        input_doc_content: Dict[str, Any],
        ref_doc_content: Dict[str, Any],
        **scenario_params: Any
    ) -> CompareResponse:
        """Asynchronous version using ``httpx`` if available."""
        if self._async_client is None:
            raise RuntimeError("httpx is not installed")
        payload = {
            "project_id": project_id,
            "input_data": {
                "level1": [
                    {
                        "sid": f"input_{project_id}",
                        "text": input_doc_content,
                        "metadata": {"project": project_id}
                    }
                ]
            },
            "reference_data": {
                "level1": [
                    {
                        "sid": f"ref_{project_id}",
                        "text": ref_doc_content,
                        "metadata": {"project": project_id}
                    }
                ]
            },
            "scenario": scenario_params,
        }
        resp = await self._async_client.post("/api/v1/rag", json=payload)
        resp.raise_for_status()
        obj = resp.json()
        return CompareResponse(result=obj.get("result", ""))

    async def aclose(self) -> None:
        """Close the underlying async client if used."""
        if self._async_client is not None:
            await self._async_client.aclose()
