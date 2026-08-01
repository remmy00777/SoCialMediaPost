from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings


class SecurityError(RuntimeError):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64)
        expected = base64.urlsafe_b64decode(digest_b64)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class KeyManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.secret_dir = self.settings.storage_root / ".secrets"
        self.secret_file = self.secret_dir / "encryption.key"

    def get_or_create_key(self) -> bytes:
        if self.settings.encryption_key:
            return self.settings.encryption_key.encode()
        key = self._read_macos_keychain()
        if key:
            return key
        if self.secret_file.exists():
            return self.secret_file.read_bytes().strip()
        key = Fernet.generate_key()
        if self._write_macos_keychain(key):
            return key
        self.secret_dir.mkdir(parents=True, exist_ok=True)
        self.secret_file.write_bytes(key)
        self.secret_file.chmod(0o600)
        return key

    def _read_macos_keychain(self) -> bytes | None:
        if os.uname().sysname != "Darwin":
            return None
        result = subprocess.run(
            ["security", "find-generic-password", "-s", self.settings.keychain_service, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip().encode() if result.returncode == 0 else None

    def _write_macos_keychain(self, key: bytes) -> bool:
        if os.uname().sysname != "Darwin":
            return False
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                self.settings.keychain_service,
                "-a",
                os.getenv("USER", "local-user"),
                "-w",
                key.decode(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0


class SecretBox:
    def __init__(self, key: bytes | None = None) -> None:
        self.fernet = Fernet(key or KeyManager().get_or_create_key())

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self.fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise SecurityError("Unable to decrypt stored secret") from exc


class SessionSigner:
    def __init__(self, secret: str | None = None) -> None:
        self.secret = (secret or get_settings().session_secret).encode()

    def issue(self, subject: str, ttl_minutes: int | None = None) -> str:
        ttl = ttl_minutes or get_settings().session_ttl_minutes
        payload = {
            "sub": subject,
            "exp": int((datetime.now(UTC) + timedelta(minutes=ttl)).timestamp()),
            "nonce": secrets.token_urlsafe(12),
        }
        raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        signature = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
        return f"{raw}.{signature}"

    def verify(self, token: str) -> dict[str, Any]:
        try:
            raw, signature = token.rsplit(".", 1)
            expected = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise SecurityError("Invalid session signature")
            payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
            if int(payload["exp"]) < int(datetime.now(UTC).timestamp()):
                raise SecurityError("Session expired")
            return payload
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise SecurityError("Invalid session") from exc


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def secure_filename(value: str, max_length: int = 120) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)
    normalized = normalized.strip("._") or "file"
    return normalized[:max_length]
