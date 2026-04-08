"""
main.py - FastAPI 应用入口
Phase 2 运维增强版本
Phase 3 性能优化版本
"""
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api import api_router
from app.api.websocket import websocket_endpoint
from app.logging_config import setup_logging
from app.rate_limit import limiter
from app.api.health import router as health_router

# 应用启动时初始化日志
setup_logging(settings.DEBUG)
# 安全头中间件
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="人脸识别门禁考勤系统",
        description="""
        ## 功能特性
        - 🔐 JWT 认证 + RBAC 角色权限控制
        - 👤 人脸注册与识别
        - 📋 考勤签到/签退记录
        - 📍 多门禁设备管理
        - 📊 考勤统计与趋势分析
        - 🔔 实时通知推送
        - 👤 用户自助服务
        - 📈 Prometheus 监控指标
        
        ## 角色说明
        | 角色 | 权限 |
        |------|------|
        | super_admin | 全部权限 |
        | dept_admin | 部门管理 + 设备管理 |
        | employee | 个人考勤查看 + 人脸注册 |
        """,
        version="2.1.0",
        debug=settings.DEBUG,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    @app.on_event("startup")
    async def startup_event():
        # Phase 3 性能优化：启动时初始化数据库索引
        from app.database import ensure_indexes
        ensure_indexes()

    app.include_router(api_router)
    app.include_router(health_router)

    return app


app = create_app()


# Prometheus 监控埋点
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/health/ready", "/health/live", "/metrics", "/docs", "/openapi.json", "/redoc"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.websocket("/ws/face-stream")
async def ws_face_stream(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/")
def root():
    return {"message": "Face Scan API", "version": "2.1.0"}
