from __future__ import annotations

import random
import time
from typing import Any

import httpx


class PlatformAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ResilientHTTPClient:
    def __init__(self, timeout: float = 30.0, max_attempts: int = 3) -> None:
        self.timeout = timeout
        self.max_attempts = max_attempts

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                    response = client.request(method, url, **kwargs)
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt < self.max_attempts:
                        retry_after = response.headers.get("retry-after")
                        delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt - 1)
                        time.sleep(delay + random.uniform(0, 0.25))
                        continue
                if response.is_error:
                    try:
                        payload: Any = response.json()
                    except ValueError:
                        payload = response.text[:500]
                    raise PlatformAPIError(
                        f"Platform API request failed with HTTP {response.status_code}",
                        status_code=response.status_code,
                        payload=payload,
                    )
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.25))
                    continue
        raise PlatformAPIError("Platform API request failed after retries") from last_error
