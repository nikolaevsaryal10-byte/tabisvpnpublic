import os
import base64
import secrets
import hashlib
from typing import List
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from config import AES_KEY, AES_IV, SERVERS_FILE

def hash_user_password(password: str) -> str:
    """Secure SHA-256 password hash with salt."""
    salt = os.getenv("AUTH_SALT", "TabisUserAuthSalt_ChangeInProduction!")
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

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
