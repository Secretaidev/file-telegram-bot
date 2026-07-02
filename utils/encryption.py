"""
vault bot — encryption layer
symmetric encryption for vault file metadata using fernet
"""

from __future__ import annotations
import base64
import hashlib
from cryptography.fernet import Fernet
from config import cfg


def _derive_key(secret: str) -> bytes:
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


_fernet = Fernet(_derive_key(cfg.VAULT_SECRET))


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    return _fernet.decrypt(data)
