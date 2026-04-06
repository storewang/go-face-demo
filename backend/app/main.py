from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router
from app.api.websocket import websocket_endpoint

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws/face-stream")
async def ws_face_stream(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/")
def root():
    return {"message": "Face Scan API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
