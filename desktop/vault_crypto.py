import os
import json
import base64
import time
from typing import Dict, Any, List, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

class VaultCrypto:
    """
    Standard AES-256-GCM + PBKDF2-HMAC-SHA256 Encryption Engine.
    Compatible across Python (Desktop) and Android (Jetpack / Java Cryptography).
    """
    SALT_LEN = 16
    IV_LEN = 12
    ITERATIONS = 100_000
    KEY_LEN = 32 # 256 bits

    @classmethod
    def derive_key(cls, master_password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_LEN,
            salt=salt,
            iterations=cls.ITERATIONS
        )
        return kdf.derive(master_password.encode('utf-8'))

    @classmethod
    def encrypt(cls, plaintext_json: str, master_password: str) -> Dict[str, Any]:
        salt = os.urandom(cls.SALT_LEN)
        iv = os.urandom(cls.IV_LEN)
        key = cls.derive_key(master_password, salt)
        aesgcm = AESGCM(key)
        
        ciphertext = aesgcm.encrypt(iv, plaintext_json.encode('utf-8'), None)
        
        return {
            "version": 1,
            "kdf": "PBKDF2HMAC-SHA256",
            "cipher": "AES-256-GCM",
            "iterations": cls.ITERATIONS,
            "salt": base64.b64encode(salt).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "data": base64.b64encode(ciphertext).decode('utf-8'),
            "updated_at": int(time.time())
        }

    @classmethod
    def decrypt(cls, vault_envelope: Dict[str, Any], master_password: str) -> str:
        salt = base64.b64decode(vault_envelope["salt"])
        iv = base64.b64decode(vault_envelope["iv"])
        ciphertext = base64.b64decode(vault_envelope["data"])
        
        key = cls.derive_key(master_password, salt)
        aesgcm = AESGCM(key)
        
        plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)
        return plaintext_bytes.decode('utf-8')
