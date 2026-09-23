import os
import base64
import secrets
import hashlib
from typing import List, Tuple, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from config import AES_KEY, AES_IV, SERVERS_FILE

# Cryptographically hardened Argon2id password hasher
# time_cost=2, memory_cost=64MB, parallelism=1 (OWASP recommended parameters)
_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)

def hash_user_password(password: str) -> str:
    """Secure Argon2id password hash."""
    return _ph.hash(password)

def verify_and_migrate_password(stored_hash: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Verifies user password against stored database hash.
    Supports modern Argon2id ($argon2id$...) and transparently verifies & migrates
    legacy SHA-256 password hashes to Argon2id upon successful authentication.
    Returns: (is_valid, new_argon2_hash_or_none)
    """
    if not stored_hash or not password:
        return False, None

    if stored_hash.startswith("$argon2"):
        try:
            if _ph.verify(stored_hash, password):
                if _ph.check_needs_rehash(stored_hash):
                    return True, _ph.hash(password)
                return True, None
        except (VerifyMismatchError, InvalidHashError):
            return False, None
        except Exception:
            return False, None

    # Legacy SHA-256 fallback with salt
    configured_salt = os.getenv("AUTH_SALT", "TabisUserAuthSalt2026_Secure!")
    legacy_hash = hashlib.sha256((password + configured_salt).encode('utf-8')).hexdigest()
    if secrets.compare_digest(stored_hash, legacy_hash):
        new_hash = _ph.hash(password)
        return True, new_hash

    # Secondary check with legacy static fallback if AUTH_SALT was overridden
    old_default_salt = "TabisUserAuthSalt2026_Secure!"
    if configured_salt != old_default_salt:
        old_legacy_hash = hashlib.sha256((password + old_default_salt).encode('utf-8')).hexdigest()
        if secrets.compare_digest(stored_hash, old_legacy_hash):
            new_hash = _ph.hash(password)
            return True, new_hash

    return False, None

def generate_user_code() -> str:
    """Generates exactly 16-character unique user account code, e.g. A8F1-7C3D-E5F6-0B24."""
    part = secrets.token_hex(8).upper()
    return f"{part[:4]}-{part[4:8]}-{part[8:12]}-{part[12:16]}"

def generate_device_token() -> str:
    """Generates unique device token in format TABIS-XXXX-XXXX (e.g. TABIS-ACDB-DD58)."""
    p1 = secrets.token_hex(2).upper()
    p2 = secrets.token_hex(2).upper()
    return f"TABIS-{p1}-{p2}"

def generate_referral_code() -> str:
    part = secrets.token_hex(4).upper()
    return f"TABIS-REFERAL-{part[:4]}-{part[4:]}"

def encrypt_aes_cbc_pkcs7(plain_text: str) -> str:
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain_text.encode('utf-8')) + padder.finalize()
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    encryptor = cipher.encryptor()
    cipher_bytes = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(cipher_bytes).decode('utf-8')

def load_server_keys() -> List[str]:
    if not os.path.exists(SERVERS_FILE):
        return []
    keys = []
    with open(SERVERS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                keys.append(line)
    return keys
