from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Face Scan API"
    DEBUG: bool = True

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

    # Admin
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"


settings = Settings()
