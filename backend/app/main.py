"""
main.py - FastAPI 应用入口
Phase 2 运维增强版本
Phase 3 性能优化版本
"""
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from secure import SecureHeaders
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.api import api_router
from app.api.websocket import websocket_endpoint
from app.logging_config import setup_logging
from app.api.health import router as health_router

# 应用启动时初始化日志
setup_logging(settings.DEBUG)

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
secure_headers = SecureHeaders()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

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

    @app.middleware("http")
    async def add_secure_headers(request: Request, call_next):
        response = await call_next(request)
        secure_headers.starlette(response)
        return response

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
    return {"message": "Face Scan API", "version": "2.0.0"}


@app.get("/health")
def health_check():
    """兼容旧版 /health 端点"""
    return {"status": "healthy", "version": "2.0.0"}
