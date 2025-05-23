from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict
from urllib import request


@dataclass
class CompareResponse:
    """Simple response model for API results."""
    result: str


class ApiClient:
    """Minimal HTTP client using urllib."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

    def compare(self, input_doc: Dict[str, Any], ref_doc: Dict[str, Any], **params: Any) -> CompareResponse:
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
