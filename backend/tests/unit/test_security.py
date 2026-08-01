from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.core.security import SecretBox, SecurityError, SessionSigner, hash_password, secure_filename, verify_password


def test_password_hash_roundtrip():
    encoded = hash_password("strong-password")
    assert encoded != "strong-password"
    assert verify_password("strong-password", encoded)
    assert not verify_password("wrong", encoded)


def test_session_signer_roundtrip_and_tamper():
    signer = SessionSigner("x" * 32)
    token = signer.issue("user-1", ttl_minutes=5)
    assert signer.verify(token)["sub"] == "user-1"
    with pytest.raises(SecurityError):
        signer.verify(token + "tamper")


def test_secret_box_roundtrip():
    box = SecretBox(Fernet.generate_key())
    cipher = box.encrypt("token-value")
    assert "token-value" not in cipher
    assert box.decrypt(cipher) == "token-value"


def test_secure_filename_blocks_paths():
    value = secure_filename("../../secret; rm -rf /")
    assert "/" not in value
    assert ".." not in value
