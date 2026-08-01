from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(slots=True)
class NotificationResult:
    delivered: bool
    channel: str
    error: str | None = None


class NotificationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send_macos(self, title: str, message: str) -> NotificationResult:
        if not self.settings.macos_notifications:
            return NotificationResult(False, "macos", "disabled")
        if os.uname().sysname != "Darwin":
            return NotificationResult(False, "macos", "not_running_on_macos")
        safe_title = title.replace('"', "'")[:120]
        safe_message = message.replace('"', "'")[:300]
        result = subprocess.run(
            ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
            capture_output=True,
            text=True,
            check=False,
        )
        return NotificationResult(result.returncode == 0, "macos", result.stderr.strip() or None)
