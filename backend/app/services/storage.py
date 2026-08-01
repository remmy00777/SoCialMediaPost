from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.security import secure_filename


REQUIRED_TREE = [
    "trends/raw",
    "trends/normalized",
    "trends/analyses",
    "trends/archived",
    "trends/source_references",
    "generated/TikTok/drafts",
    "generated/TikTok/ready_to_post",
    "generated/TikTok/published",
    "generated/TikTok/failed",
    "generated/Instagram/drafts",
    "generated/Instagram/ready_to_post",
    "generated/Instagram/published",
    "generated/Instagram/failed",
    "generated/YouTube/drafts",
    "generated/YouTube/ready_to_post",
    "generated/YouTube/published",
    "generated/YouTube/failed",
    "Ready to Post for TikTok",
    "Ready to Post for Instagram",
    "Ready to Post for YouTube",
    "analytics",
    "experiments",
    "reports",
    "logs",
    "exports",
    "temporary",
    "quarantine",
    "backups",
]

PLATFORM_DISPLAY = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}


class StorageManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.storage_root.resolve()
        self.initialize()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for relative in REQUIRED_TREE:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def ensure_inside_root(self, path: Path) -> Path:
        resolved = path.resolve()
        if self.root != resolved and self.root not in resolved.parents:
            raise ValueError("Path traversal attempt blocked")
        return resolved

    def atomic_write_text(self, path: Path, content: str) -> Path:
        path = self.ensure_inside_root(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path

    def atomic_write_json(self, path: Path, payload: Any) -> Path:
        return self.atomic_write_text(path, json.dumps(payload, indent=2, default=str, ensure_ascii=False))

    def atomic_copy(self, source: Path, destination: Path) -> Path:
        destination = self.ensure_inside_root(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copy2(source, temp_name)
            os.replace(temp_name, destination)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return destination

    def package_dir(self, platform: str, status: str, package_id: str) -> Path:
        display = PLATFORM_DISPLAY[platform]
        safe_id = secure_filename(package_id)
        directory = self.root / "generated" / display / status / safe_id
        return self.ensure_inside_root(directory)

    def ready_mirror_dir(self, platform: str, package_id: str) -> Path:
        display = PLATFORM_DISPLAY[platform]
        return self.ensure_inside_root(self.root / f"Ready to Post for {display}" / secure_filename(package_id))

    def move_package(self, platform: str, package_id: str, source_status: str, target_status: str) -> Path:
        source = self.package_dir(platform, source_status, package_id)
        target = self.package_dir(platform, target_status, package_id)
        if not source.exists():
            raise FileNotFoundError(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        os.replace(source, target)
        return target

    def mirror_ready_package(self, platform: str, package_dir: Path, package_id: str) -> Path:
        mirror = self.ready_mirror_dir(platform, package_id)
        if mirror.exists():
            shutil.rmtree(mirror)
        shutil.copytree(package_dir, mirror)
        return mirror


    def source_media_dir(self, candidate_id: str) -> Path:
        directory = self.root / "trends" / "source_references" / secure_filename(candidate_id)
        directory.mkdir(parents=True, exist_ok=True)
        return self.ensure_inside_root(directory)

    def delete_source_media(self, candidate_id: str) -> dict[str, int]:
        directory = self.source_media_dir(candidate_id)
        return self._remove_tree(directory)

    def delete_content_package(self, package_id: str) -> dict[str, int]:
        safe_id = secure_filename(package_id)
        totals = {"files_deleted": 0, "bytes_freed": 0, "directories_deleted": 0}
        for display in PLATFORM_DISPLAY.values():
            for status in ("drafts", "ready_to_post", "published", "failed", "quarantine", "archived"):
                directory = self.ensure_inside_root(self.root / "generated" / display / status / safe_id)
                self._add_delete_stats(totals, self._remove_tree(directory))
            mirror = self.ensure_inside_root(self.root / f"Ready to Post for {display}" / safe_id)
            self._add_delete_stats(totals, self._remove_tree(mirror))
        return totals

    @staticmethod
    def _add_delete_stats(total: dict[str, int], current: dict[str, int]) -> None:
        for key in total:
            total[key] += current.get(key, 0)

    def _remove_tree(self, directory: Path) -> dict[str, int]:
        directory = self.ensure_inside_root(directory)
        if not directory.exists():
            return {"files_deleted": 0, "bytes_freed": 0, "directories_deleted": 0}
        files = [path for path in directory.rglob("*") if path.is_file()]
        size = sum(path.stat().st_size for path in files)
        directories = sum(1 for path in directory.rglob("*") if path.is_dir()) + 1
        shutil.rmtree(directory)
        return {"files_deleted": len(files), "bytes_freed": size, "directories_deleted": directories}

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def storage_usage(self) -> dict[str, int]:
        files = [path for path in self.root.rglob("*") if path.is_file()]
        total = sum(path.stat().st_size for path in files)
        stat = shutil.disk_usage(self.root)
        return {
            "used_bytes": total,
            "file_count": len(files),
            "disk_free_bytes": stat.free,
            "disk_total_bytes": stat.total,
        }
