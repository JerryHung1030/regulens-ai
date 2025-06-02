# app/mock_api_client.py
from __future__ import annotations
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass
from random import choice   # 也可以改成 round-robin 或自訂
from .api_client import CompareResponse


@dataclass
class _MockResp:
    """把 Good / Bad case JSON 讀進來後，拿 result 欄位就好"""
    result: str


class MockApiClient:
    """
    模擬 /api/v1/rag 系列端點。呼叫 compare / acompare
    會回傳預先載入的假資料，而不用真的打 API。
    """
    def __init__(self,
                 mock_dir: str | Path = "sample_data/mock_responses",
                 latency: float = 0.05) -> None:
        self.latency = latency              # 模擬網路延遲
        self.payloads: List[Dict[str, Any]] = []
        mock_dir = Path(mock_dir)
        for p in sorted(mock_dir.glob("*.json")):
            self.payloads.append(json.loads(p.read_text(encoding="utf-8")))
        if not self.payloads:
            # 保底：沒有檔案時也能運行
            self.payloads.append({"result": "(empty mock)"})

    # ---------- 與 ApiClient 介面一致即可 ---------- #
    # 為了對應 CompareManager 及測試，需要跟 ApiClient 同一個方法簽名：
    def compare(
        self,
        project_id: str,
        input_doc_content: Dict[str, Any],
        ref_doc_content: Dict[str, Any],
        **scenario_params: Any
    ) -> CompareResponse:
        """
        模擬 compare：
        從 self.payloads 隨機拿一筆 mock data，讀取 result / status / progress。
        現階段 GUI 用不到 status/progress，但預留。
        """
        data = choice(self.payloads)
        # 假定 mock JSON 可能有 "status", "progress", "result"
        # CompareResponse 目前只有 "result" 欄位；GUI 只顯示 result
        mock_result = data.get("result", "(mock no result)")
        return CompareResponse(result=mock_result)

    async def acompare(
        self,
        project_id: str,
        input_doc_content: Dict[str, Any],
        ref_doc_content: Dict[str, Any],
        **scenario_params: Any
    ) -> CompareResponse:
        await asyncio.sleep(self.latency)   # 模擬 async request
        return self.compare(project_id, input_doc_content, ref_doc_content, **scenario_params)

    async def aclose(self):
        """讓 MainWindow 關閉時呼叫也安全；此處可不做任何事"""
        pass
