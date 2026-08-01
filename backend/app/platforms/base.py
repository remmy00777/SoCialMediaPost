from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.schemas import NormalizedVideo


@dataclass(slots=True)
class AdapterHealth:
    platform: str
    status: str
    configured: bool
    publishing_eligible: bool = False
    analytics_eligible: bool = False
    limitations: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class PlatformAdapter(ABC):
    platform: str

    @abstractmethod
    def connect_account(self, state: str) -> str: ...

    @abstractmethod
    def disconnect_account(self, account_id: str) -> None: ...

    @abstractmethod
    def refresh_authorization(self, refresh_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def verify_permissions(self, access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def discover_trends(self, limit: int = 30) -> list[NormalizedVideo]: ...

    @abstractmethod
    def import_video_reference(self, url: str) -> NormalizedVideo: ...

    @abstractmethod
    def retrieve_video_metadata(self, video_id: str, access_token: str | None = None) -> NormalizedVideo: ...

    @abstractmethod
    def retrieve_account_metrics(self, access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def retrieve_post_metrics(self, post_id: str, access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def validate_media(self, path: Path) -> dict[str, Any]: ...

    @abstractmethod
    def create_draft(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def upload_media(self, path: Path, metadata: dict[str, Any], access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def publish_media(self, upload_id: str, metadata: dict[str, Any], access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def retrieve_publish_status(self, publish_id: str, access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def delete_pending_upload(self, upload_id: str, access_token: str) -> dict[str, Any]: ...

    @abstractmethod
    def handle_webhook(self, payload: dict[str, Any], signature: str | None) -> dict[str, Any]: ...

    @abstractmethod
    def health_check(self) -> AdapterHealth: ...
