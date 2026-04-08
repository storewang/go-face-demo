"""
对象存储服务
兼容 MinIO / S3 / 阿里云 OSS
降级策略：不可用时回退到本地文件存储
"""
import io
from pathlib import Path
from typing import Optional

from app.config import settings
import structlog

log = structlog.get_logger(__name__)


class StorageService:
    def __init__(self):
        self._minio_client = None
        self._available = False
        self._local_dir = settings.IMAGES_DIR
        self._init_client()

    def _init_client(self):
        if not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
            log.info("storage_mode", mode="local", reason="S3 credentials not configured")
            return
        try:
            from minio import Minio
            self._minio_client = Minio(
                settings.S3_ENDPOINT,
                access_key=settings.S3_ACCESS_KEY,
                secret_key=settings.S3_SECRET_KEY,
                secure=settings.S3_USE_SSL,
            )
            self._ensure_buckets()
            self._available = True
            log.info("storage_mode", mode="minio", endpoint=settings.S3_ENDPOINT)
        except Exception as e:
            log.warning("storage_init_failed", error=str(e), fallback="local")

    def _ensure_buckets(self):
        for bucket in [settings.S3_FACE_BUCKET, settings.S3_ENCODING_BUCKET, settings.S3_SNAPSHOT_BUCKET]:
            if not self._minio_client.bucket_exists(bucket):
                self._minio_client.make_bucket(bucket)

    @property
    def available(self) -> bool:
        return self._available

    def upload(self, bucket: str, object_name: str, data: bytes, content_type: str = "application/octet-stream"):
        if self._available:
            try:
                self._minio_client.put_object(bucket, object_name, io.BytesIO(data), len(data), content_type=content_type)
                return
            except Exception as e:
                log.warning("storage_upload_failed", bucket=bucket, error=str(e), fallback="local")
        local_path = self._local_dir / bucket / object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)

    def download(self, bucket: str, object_name: str) -> Optional[bytes]:
        if self._available:
            try:
                response = self._minio_client.get_object(bucket, object_name)
                data = response.read()
                response.close()
                response.release_conn()
                return data
            except Exception as e:
                log.warning("storage_download_failed", bucket=bucket, error=str(e), fallback="local")
        local_path = self._local_dir / bucket / object_name
        if local_path.exists():
            return local_path.read_bytes()
        return None

    def delete(self, bucket: str, object_name: str):
        if self._available:
            try:
                self._minio_client.remove_object(bucket, object_name)
                return
            except Exception as e:
                log.warning("storage_delete_failed", bucket=bucket, error=str(e))
        local_path = self._local_dir / bucket / object_name
        if local_path.exists():
            local_path.unlink()

    def exists(self, bucket: str, object_name: str) -> bool:
        if self._available:
            try:
                self._minio_client.stat_object(bucket, object_name)
                return True
            except Exception:
                return False
        local_path = self._local_dir / bucket / object_name
        return local_path.exists()


storage_service = StorageService()