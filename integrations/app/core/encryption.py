"""AES-256-GCM token encryption and key derivation module.

Provides authenticated encryption at rest for OAuth access and refresh tokens.
Keys are deterministically derived from the application SECRET_KEY via HKDF-SHA256,
and every encryption operation generates a unique 96-bit initialization vector (IV).
Additional Authenticated Data (AAD) binds the ciphertext to the user and provider.
"""
from __future__ import annotations

import base64
import os
import re
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class TokenEncryptionError(Exception):
    """Raised when token encryption or decryption fails."""
    pass


class TokenVault:
    """Authenticated encryption engine using AES-256-GCM with HKDF key derivation."""

    def __init__(self, master_secret: str, salt: bytes = b"contextiq-phase5-oauth-salt"):
        if not master_secret or len(master_secret) < 8:
            raise ValueError("Master secret must be at least 8 characters long.")
        self._master_secret = master_secret
        self._salt = salt
        self._key = self._derive_key(master_secret, salt)
        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def _derive_key(secret: str, salt: bytes) -> bytes:
        """Derive a 256-bit key using HKDF-SHA256."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"contextiq-token-encryption-v1",
        )
        return hkdf.derive(secret.encode("utf-8"))

    def encrypt(self, plaintext: str, associated_data: str = "") -> bytes:
        """Encrypt plaintext string into authenticated binary payload (IV + Ciphertext + Tag)."""
        if not plaintext:
            raise ValueError("Plaintext cannot be empty.")
        try:
            nonce = os.urandom(12)  # 96-bit nonce
            aad_bytes = associated_data.encode("utf-8") if associated_data else b""
            ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad_bytes)
            return nonce + ciphertext
        except Exception as exc:
            raise TokenEncryptionError(f"Encryption failed: {exc}") from exc

    def decrypt(self, encrypted_payload: bytes, associated_data: str = "") -> str:
        """Decrypt authenticated binary payload back into plaintext string."""
        if not encrypted_payload or len(encrypted_payload) < 28:
            raise TokenEncryptionError("Invalid encrypted payload size: must be at least 28 bytes.")
        try:
            nonce = encrypted_payload[:12]
            ciphertext = encrypted_payload[12:]
            aad_bytes = associated_data.encode("utf-8") if associated_data else b""
            decrypted = self._aesgcm.decrypt(nonce, ciphertext, aad_bytes)
            return decrypted.decode("utf-8")
        except Exception as exc:
            raise TokenEncryptionError(f"Decryption failed or payload tampered: {exc}") from exc

    def encrypt_to_base64(self, plaintext: str, associated_data: str = "") -> str:
        """Convenience method to encrypt and return URL-safe base64 string."""
        binary = self.encrypt(plaintext, associated_data)
        return base64.urlsafe_b64encode(binary).decode("ascii")

    def decrypt_from_base64(self, base64_payload: str, associated_data: str = "") -> str:
        """Convenience method to decrypt from URL-safe base64 string."""
        try:
            binary = base64.urlsafe_b64decode(base64_payload.encode("ascii"))
            return self.decrypt(binary, associated_data)
        except Exception as exc:
            raise TokenEncryptionError(f"Base64 decryption failed: {exc}") from exc


_TOKEN_PATTERN = re.compile(r"(ya29\.[0-9a-zA-Z_-]+|eyJ[0-9a-zA-Z_-]+\.eyJ[0-9a-zA-Z_-]+\.[0-9a-zA-Z_-]+)")


def redact_secret(text: str) -> str:
    """Redact OAuth access/refresh tokens and JWT signatures from logs."""
    if not text:
        return ""
    return _TOKEN_PATTERN.sub("[REDACTED_SECRET]", text)
