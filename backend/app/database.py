"""
SQLAlchemy 数据库配置
支持连接池和自动会话管理
"""
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    上下文管理器方式的数据库会话
    适用于非 FastAPI 依赖注入场景
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ensure_indexes():
    """Phase 3 性能优化：确保关键数据库索引存在"""
    expected_indexes = {
        "attendance_logs": [
            ("idx_attendance_user_date", "user_id, created_at"),
            ("idx_attendance_created", "created_at"),
        ],
    }
    
    inspector = inspect(engine)
    
    for table_name, indexes in expected_indexes.items():
        if not inspector.has_table(table_name):
            continue
        existing = [idx["name"] for idx in inspector.get_indexes(table_name)]
        for idx_name, columns in indexes:
            if idx_name not in existing:
                try:
                    with engine.connect() as conn:
                        conn.execute(text(f"CREATE INDEX {idx_name} ON {table_name} ({columns})"))
                        conn.commit()
                        log.info("index_created", table=table_name, index=idx_name)
                except Exception as e:
                    log.warning("index_create_failed", table=table_name, index=idx_name, error=str(e))
