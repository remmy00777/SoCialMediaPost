from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import current_user
from app.api.router import router, seed_defaults
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.models import BrandProfile, User
from app.services.storage import StorageManager


settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    StorageManager(settings).initialize()
    with SessionLocal() as db:
        existing_user = db.execute(select(User)).scalars().first()

        if not existing_user:
            administrator = User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
            db.add(administrator)
            db.flush()

            db.add(
                BrandProfile(
                    user_id=administrator.id,
                    approved=settings.demo_mode,
                )
            )

        seed_defaults(db)
        db.commit()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first social-media intelligence and content operations API.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

rate_buckets: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or secrets.token_hex(12)
    client = request.client.host if request.client else "local"
    now = time.monotonic()
    bucket = rate_buckets[client]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= 240:
        return JSONResponse({"detail": "Local API rate limit exceeded"}, status_code=429)
    bucket.append(now)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' http://127.0.0.1:8765 http://localhost:8765; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred", "error_type": type(exc).__name__},
    )


app.include_router(router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/portal", StaticFiles(directory=STATIC_DIR, html=True), name="portal")


@app.get("/files/{relative_path:path}")
def managed_file(relative_path: str, _: User | None = Depends(current_user)):
    candidate = (settings.storage_root / relative_path).resolve()
    root = settings.storage_root.resolve()
    if root not in candidate.parents or not candidate.is_file():
        return JSONResponse({"detail": "File not found"}, status_code=404)
    return FileResponse(candidate)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/portal/")
