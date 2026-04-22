FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载 InsightFace 模型 (约 300MB，避免运行时下载)
ENV INSIGHTFACE_HOME=/app/.insightface
RUN python -c "\
from insightface.app import FaceAnalysis; \
app = FaceAnalysis(name='buffalo_l', root='/app'); \
app.prepare(ctx_id=-1, det_size=640); \
print('Model pre-downloaded successfully')"

COPY . .

RUN mkdir -p data/faces/images/snapshots data/faces/encodings models

EXPOSE 8000

CMD ["sh", "-c", "python -m app.init_db && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 120"]
