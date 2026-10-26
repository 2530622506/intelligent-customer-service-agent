from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import uuid4

import boto3  # type: ignore[import-untyped]
from botocore.client import Config as BotoConfig  # type: ignore[import-untyped]

from app.core.config import Settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    content_type: str
    size: int


class RustFSStorage:
    """RustFS S3 兼容适配器；同步 SDK 放在线程中，避免阻塞 FastAPI 事件循环。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.rustfs_endpoint,
            aws_access_key_id=settings.rustfs_access_key,
            aws_secret_access_key=settings.rustfs_secret_key,
            region_name="us-east-1",
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def ensure_bucket(self) -> None:
        def ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self._settings.rustfs_bucket)
            except Exception:  # noqa: BLE001  # HeadBucket 失败时尝试创建 bucket。
                self._client.create_bucket(Bucket=self._settings.rustfs_bucket)

        await asyncio.to_thread(ensure)

    async def put_bytes(self, data: bytes, filename: str, content_type: str) -> StoredObject:
        await self.ensure_bucket()
        safe_name = PurePosixPath(filename).name.replace("/", "_")
        key = f"original/{uuid4()}-{safe_name}"
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._settings.rustfs_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredObject(key=key, content_type=content_type, size=len(data))

    async def get_bytes(self, key: str) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object, Bucket=self._settings.rustfs_bucket, Key=key
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._settings.rustfs_bucket, Key=key
        )
