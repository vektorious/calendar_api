# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Don't write .pyc files into the image / buffer stdout, so logs show up immediately in `docker logs`
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so this layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# The real sources.yaml is gitignored and supplied via a bind mount or Docker
# secret at runtime (see docker-compose.yml) — never baked into the image,
# since it contains calendar URLs you don't want in a shipped image layer.
# We copy the sanitized example as a fallback so a fresh clone still builds
# and /health responds usefully even if you forget to mount a real config.
COPY sources.yaml.example ./sources.yaml.example

EXPOSE 8000

# Basic container-level healthcheck hitting the open /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
