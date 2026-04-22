"""
model_manager.py - InsightFace 模型自动下载与校验
确保 buffalo_l 模型在首次启动或 Docker 构建时自动就绪
"""
import os
import structlog
from pathlib import Path
from typing import Optional

log = structlog.get_logger(__name__)


class ModelManager:
    """InsightFace 模型生命周期管理"""

    def __init__(self, model_name: str = "buffalo_l", model_dir: Optional[str] = None):
        self.model_name = model_name
        # InsightFace 默认使用 ~/.insightface/models/ 目录
        # 也可通过 INSIGHTFACE_HOME 环境变量控制
        self.model_dir = Path(model_dir or os.environ.get(
            "INSIGHTFACE_HOME",
            Path.home() / ".insightface" / "models"
        ))
        self.model_path = self.model_dir / self.model_name

    @property
    def is_ready(self) -> bool:
        """检查模型是否已下载且完整"""
        if not self.model_path.exists():
            return False
        # buffalo_l 模型应包含以下文件
        required_files = [
            "1k3d68.onnx",
            "2d106det.onnx",
            "det_10g.onnx",
            "genderage.onnx",
            "w600k_r50.onnx",
        ]
        for f in required_files:
            if not (self.model_path / f).exists():
                return False
        return True

    def ensure_model(self) -> Path:
        """
        确保模型已下载且可用
        如果模型不存在，触发 InsightFace 自动下载机制
        """
        if self.is_ready:
            log.info("model_already_ready", path=str(self.model_path))
            return self.model_path

        log.info("model_download_start", model=self.model_name, dir=str(self.model_dir))
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # 利用 InsightFace 自带的下载机制
        # FaceAnalysis.__init__ 会在 prepare() 时自动下载
        # 这里我们只做预检查和日志，实际下载由 face_service._init_insightface 触发
        try:
            from insightface.app import FaceAnalysis
            # 创建实例并 prepare 会触发下载
            face_app = FaceAnalysis(name=self.model_name, root=str(self.model_dir.parent.parent))
            face_app.prepare(ctx_id=-1, det_size=640)  # ctx_id=-1 使用 CPU，避免构建时 GPU 问题
            log.info("model_download_complete", model=self.model_name)
        except Exception as e:
            log.error("model_download_failed", error=str(e))
            raise RuntimeError(
                f"无法下载 InsightFace 模型 '{self.model_name}': {e}\n"
                f"请检查网络连接，或手动下载模型到 {self.model_path}"
            ) from e

        if not self.is_ready:
            raise RuntimeError(
                f"模型下载后验证失败: {self.model_path}\n"
                f"预期文件不完整"
            )

        return self.model_path

    def get_model_info(self) -> dict:
        """返回模型信息摘要"""
        return {
            "name": self.model_name,
            "path": str(self.model_path),
            "ready": self.is_ready,
            "files": list(self.model_path.glob("*.onnx")) if self.model_path.exists() else [],
        }


model_manager = ModelManager()
