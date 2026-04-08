from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Face Scan API"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./data/face_scan.db"

    # Face Recognition
    FACE_THRESHOLD: float = 0.6
    LIVENESS_FRAMES: int = 5

    # Storage
    DATA_DIR: Path = Path("./data")
    FACES_DIR: Path = DATA_DIR / "faces"
    IMAGES_DIR: Path = FACES_DIR / "images"
    ENCODINGS_DIR: Path = FACES_DIR / "encodings"

    # Liveness Detection
    LIVENESS_MODEL_PATH: Path = Path("models/shape_predictor_68_face_landmarks.dat")

    # ===== Redis 缓存配置（Phase 3 性能优化） =====
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    # 缓存 TTL（秒）
    CACHE_USER_TTL: int = 600        # 用户信息缓存 10 分钟
    CACHE_RECOG_TTL: int = 3         # 同一用户识别结果缓存 3 秒
    CACHE_STATS_TTL: int = 300       # 统计数据缓存 5 分钟

    # ===== 安全配置 =====
    # 管理员密码哈希（优先使用哈希，兼容旧版明文密码）
    ADMIN_PASSWORD: Optional[str] = None  # 移除默认值，仅用于首次生成哈希
    ADMIN_PASSWORD_HASH: Optional[str] = None  # bcrypt哈希后的密码

    # JWT配置
    JWT_SECRET_KEY: str  # 必填，无默认值
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    # CORS配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:80"
    ]

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v):
        """确保JWT_SECRET_KEY不为空"""
        if not v or len(str(v).strip()) == 0:
            raise ValueError("JWT_SECRET_KEY不能为空，请设置一个随机密钥")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """支持从环境变量读取逗号分隔的字符串"""
        if isinstance(v, str):
            # 按逗号分隔并去除空白
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins if origins else ["http://localhost:5173", "http://localhost:80"]
        return v

    class Config:
        env_file = ".env"


settings = Settings()
