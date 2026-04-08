from app.database import engine, Base
from app.models import User, AttendanceLog, SystemConfig
from app.config import settings
from pathlib import Path
import structlog

log = structlog.get_logger(__name__)


def init_database():
    """创建所有表"""
    # 确保数据目录存在
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.FACES_DIR.mkdir(parents=True, exist_ok=True)
    settings.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    settings.ENCODINGS_DIR.mkdir(parents=True, exist_ok=True)

    # 创建表
    Base.metadata.create_all(bind=engine)

    # 插入默认配置
    from app.database import SessionLocal

    db = SessionLocal()

    default_configs = [
        {
            "config_key": "face_threshold",
            "config_value": "0.6",
            "description": "人脸识别阈值",
        },
        {
            "config_key": "liveness_frames",
            "config_value": "5",
            "description": "活体检测帧数",
        },
        {
            "config_key": "auto_check_out_hours",
            "config_value": "18",
            "description": "自动下班打卡时间",
        },
    ]

    for config in default_configs:
        exists = (
            db.query(SystemConfig).filter_by(config_key=config["config_key"]).first()
        )
        if not exists:
            db.add(SystemConfig(**config))

    db.commit()
    db.close()

    log.info("database_initialized")


if __name__ == "__main__":
    init_database()
