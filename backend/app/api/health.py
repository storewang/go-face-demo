"""
健康检查路由
"""
from fastapi import APIRouter, Response
from datetime import datetime
from app.config import settings

router = APIRouter(tags=["健康检查"])


@router.get("/health")
async def health_check():
    """综合健康检查"""
    checks = {}

    try:
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    try:
        from app.services.face_service import face_service
        checks["face_service"] = {
            "status": "healthy" if face_service.ready else "loading",
            "known_faces": len(face_service.known_encodings),
        }
    except Exception as e:
        checks["face_service"] = {"status": "unhealthy", "error": str(e)}

    import shutil
    disk = shutil.disk_usage("/")
    disk_percent = (disk.used / disk.total) * 100
    checks["disk"] = {
        "status": "healthy" if disk_percent < 90 else "warning" if disk_percent < 95 else "critical",
        "usage_percent": round(disk_percent, 1),
        "free_gb": round(disk.free / (1024**3), 1),
    }

    try:
        data_dir = settings.DATA_DIR
        checks["storage"] = {
            "status": "healthy" if data_dir.exists() else "unhealthy",
            "path": str(data_dir),
        }
    except Exception as e:
        checks["storage"] = {"status": "unhealthy", "error": str(e)}

    all_healthy = all(c.get("status") == "healthy" for c in checks.values())
    has_critical = any(c.get("status") == "unhealthy" for c in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded" if not has_critical else "unhealthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks,
        "version": "2.0.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """K8s readinessProbe - 检查数据库连接"""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"ready": True}
    except Exception:
        return Response(content='{"ready": false}', media_type="application/json", status_code=503)


@router.get("/health/live")
async def liveness_check():
    """K8s livenessProbe"""
    return {"alive": True}
