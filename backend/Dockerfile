FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates libmagic1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
RUN python -m pip install --no-cache-dir .
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY fixtures /app/fixtures
EXPOSE 8765
CMD ["uvicorn","app.main:app","--host","127.0.0.1","--port","8765","--proxy-headers"]
