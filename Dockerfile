FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    pkg-config \
    ffmpeg \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libopenblas-dev \
    liblapack-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src ./src

RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install ".[frontend]"

EXPOSE 8501

CMD ["vidxp", "ui", "--host", "0.0.0.0", "--port", "8501"]
