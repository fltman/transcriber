import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

VERIFY_PLAINTEXT = "transcriber-encryption-verify"


class EncryptionService:
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive a Fernet key from password + salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    @staticmethod
    def encrypt_text(text: str, key: bytes) -> str:
        """Encrypt plaintext, return base64-encoded ciphertext."""
        f = Fernet(key)
        return f.encrypt(text.encode()).decode()

    @staticmethod
    def decrypt_text(encrypted: str, key: bytes) -> str:
        """Decrypt ciphertext back to plaintext."""
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()

    @staticmethod
    def make_verify_token(key: bytes) -> str:
        """Create a verification token to later check if password is correct."""
        f = Fernet(key)
        return f.encrypt(VERIFY_PLAINTEXT.encode()).decode()

    @staticmethod
    def check_password(password: str, salt_b64: str, verify_token: str) -> bool:
        """Check if password is correct by decrypting the verify token."""
        salt = base64.b64decode(salt_b64)
        key = EncryptionService.derive_key(password, salt)
        try:
            f = Fernet(key)
            result = f.decrypt(verify_token.encode()).decode()
            return result == VERIFY_PLAINTEXT
        except InvalidToken:
            return False

    @staticmethod
    def generate_salt() -> bytes:
        return os.urandom(16)
