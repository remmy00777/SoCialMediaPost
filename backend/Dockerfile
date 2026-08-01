FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app

RUN python -m pip install --no-cache-dir .

COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY fixtures /app/fixtures

RUN mkdir -p /data/storage

EXPOSE 8765

CMD ["python", "-m", "app.railway_entrypoint"]
