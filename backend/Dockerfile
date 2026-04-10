FROM python:3.8-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/faces/images/snapshots data/faces/encodings models

EXPOSE 8000

CMD ["sh", "-c", "python -m app.init_db && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 120"]
