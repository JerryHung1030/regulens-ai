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
    """HTTP client for the RAGCore-X API.

    By default a minimal urllib implementation is used so the library works
    without optional dependencies. If ``httpx`` is available, the
    :py:meth:`acompare` method can be used for asynchronous requests.
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
        self, input_doc: Dict[str, Any], ref_doc: Dict[str, Any], **params: Any
    ) -> CompareResponse:
        """Perform a synchronous comparison request using ``urllib``."""
        payload = {"input": input_doc, "reference": ref_doc, **params}
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/compare",
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
        self, input_doc: Dict[str, Any], ref_doc: Dict[str, Any], **params: Any
    ) -> CompareResponse:
        """Asynchronous version using ``httpx`` if available."""
        if self._async_client is None:
            raise RuntimeError("httpx is not installed")
        payload = {"input": input_doc, "reference": ref_doc, **params}
        resp = await self._async_client.post("/v1/compare", json=payload)
        resp.raise_for_status()
        obj = resp.json()
        return CompareResponse(result=obj.get("result", ""))

    async def aclose(self) -> None:
        """Close the underlying async client if used."""
        if self._async_client is not None:
            await self._async_client.aclose()
