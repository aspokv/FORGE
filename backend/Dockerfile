# FORGE backend — FastAPI + uvicorn
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl serve ao healthcheck do compose
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Roda sem privilegio de root
RUN useradd --create-home --uid 10001 forge && chown -R forge:forge /app
USER forge

EXPOSE 8000

# server.py exige MONGO_URL e DB_NAME no import; sem eles o container morre no boot.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
