from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from secure import SecureHeaders

from app.config import settings
from app.api import api_router
from app.api.websocket import websocket_endpoint

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
    
    app.include_router(api_router)
    
    return app


app = create_app()


@app.websocket("/ws/face-stream")
async def ws_face_stream(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/")
def root():
    return {"message": "Face Scan API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
