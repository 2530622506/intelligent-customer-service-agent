from __future__ import annotations

import asyncio
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, cast
from uuid import uuid4

import httpx

from app.core.config import Settings


class MineruError(RuntimeError):
    """MinerU Cloud 返回错误或轮询超时。"""


@dataclass(frozen=True)
class ParsedDocument:
    markdown: str
    structure: dict[str, Any]
    parser_version: str


class MineruClient:
    """对齐 knowledge-hub 的 MinerU v4 file-urls/batch 流程。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def parse(self, filename: str, data: bytes) -> ParsedDocument:
        if not self._settings.mineru_api_key:
            raise MineruError("未配置 MINERU_API_KEY")
        base_url = self._settings.mineru_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {self._settings.mineru_api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            batch = await self._request_json(
                client,
                f"{base_url}/api/v4/file-urls/batch",
                headers=headers,
                json={
                    "files": [{"name": PurePosixPath(filename).name, "data_id": str(uuid4())}],
                    "model_version": self._settings.mineru_model_version,
                    "enable_formula": self._settings.mineru_enable_formula,
                    "enable_table": self._settings.mineru_enable_table,
                    "language": self._settings.mineru_language,
                },
            )
            batch_id = batch.get("batch_id")
            upload_url = (batch.get("file_urls") or [None])[0]
            if not batch_id or not upload_url:
                raise MineruError("MinerU 未返回 batch_id 或上传链接")
            upload = await client.put(upload_url, content=data, timeout=120)
            upload.raise_for_status()
            result = await self._poll(client, base_url, headers, batch_id)
            zip_url = result.get("full_zip_url")
            if not zip_url:
                raise MineruError("MinerU 结果缺少 full_zip_url")
            archive = await client.get(zip_url, timeout=120)
            archive.raise_for_status()
        return self._read_archive(archive.content)

    async def _poll(
        self, client: httpx.AsyncClient, base_url: str, headers: dict[str, str], batch_id: str
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + self._settings.mineru_poll_timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            payload = await self._request_json(
                client, f"{base_url}/api/v4/extract-results/batch/{batch_id}", headers=headers
            )
            item = cast(dict[str, Any], (payload.get("extract_result") or [{}])[0])
            state = item.get("state")
            if state == "done":
                return item
            if state in {"failed", "error"}:
                raise MineruError(str(item.get("err_msg") or "MinerU 解析失败"))
            await asyncio.sleep(self._settings.mineru_poll_interval_ms / 1000)
        raise MineruError("MinerU 解析轮询超时")

    @staticmethod
    async def _request_json(client: httpx.AsyncClient, url: str, **kwargs: Any) -> dict[str, Any]:
        response = await client.post(url, **kwargs) if "json" in kwargs else await client.get(url, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (None, 0):
            raise MineruError(str(payload.get("msg") or "MinerU 请求失败"))
        return cast(dict[str, Any], payload.get("data") or payload)

    @staticmethod
    def _read_archive(data: bytes) -> ParsedDocument:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            markdown_name = next((name for name in archive.namelist() if name.endswith("full.md")), None)
            if not markdown_name:
                raise MineruError("MinerU zip 中缺少 full.md")
            markdown = archive.read(markdown_name).decode("utf-8", errors="replace").strip()
        if not markdown:
            raise MineruError("MinerU 返回空 Markdown")
        return ParsedDocument(
            markdown=markdown,
            structure={"source": "mineru", "archive_markdown": markdown_name},
            parser_version="mineru-cloud-v4",
        )
