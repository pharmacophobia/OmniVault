import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from vault_crypto import VaultCrypto
from vision_extractor import VisionExtractor
from pico_bridge import PicoTyperBridge

DEFAULT_VAULT_PATH = os.path.expanduser("~/.omnivault/vault.enc")

class VaultManager:
    """
    Coordinates local encrypted vault storage, memory decryption state,
    and credential entries.
    """
    def __init__(self, vault_path: str = DEFAULT_VAULT_PATH):
        self.vault_path = vault_path
        self.master_password: Optional[str] = None
        self.entries: List[Dict[str, Any]] = []
        self.is_unlocked: bool = False
        self.vision_extractor = VisionExtractor()
        self.pico_bridge = PicoTyperBridge()
        # Automatically connect to Pico on startup if available
        self.pico_bridge.connect_serial()

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)

    def has_vault_file(self) -> bool:
        return os.path.exists(self.vault_path) and os.path.getsize(self.vault_path) > 0

    def is_vault_loaded(self) -> bool:
        return self.is_unlocked

    def get_encrypted_envelope(self) -> Dict[str, Any]:
        if not self.has_vault_file():
            return {}
        with open(self.vault_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_encrypted_envelope_from_remote(self, envelope: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            # Basic validation
            for req in ["salt", "iv", "data", "cipher"]:
                if req not in envelope:
                    return False, f"Missing required envelope field: {req}"

            # If unlocked, verify that master password can decrypt this incoming payload
            if self.is_unlocked and self.master_password:
                try:
                    decrypted_text = VaultCrypto.decrypt(envelope, self.master_password)
                    new_entries = json.loads(decrypted_text)
                    self.entries = new_entries
                except Exception as e:
                    return False, f"Incoming envelope cannot be decrypted with active master key: {e}"

            with open(self.vault_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2)
            return True, "Vault updated successfully"
        except Exception as e:
            return False, f"Failed to save remote vault: {str(e)}"

    def create_new_vault(self, master_password: str) -> Tuple[bool, str]:
        if self.has_vault_file():
            return False, "Vault already exists. Unlock or backup first."
        if len(master_password) < 6:
            return False, "Master password must be at least 6 characters."

        self.master_password = master_password
        self.entries = []
        self.is_unlocked = True

        ok, msg = self.save_vault()
        return ok, msg

    def unlock_vault(self, master_password: str) -> Tuple[bool, str]:
        if not self.has_vault_file():
            return False, "No existing vault file found."

        try:
            with open(self.vault_path, "r", encoding="utf-8") as f:
                envelope = json.load(f)

            plaintext = VaultCrypto.decrypt(envelope, master_password)
            self.entries = json.loads(plaintext)
            self.master_password = master_password
            self.is_unlocked = True
            return True, f"Unlocked successfully. {len(self.entries)} entries loaded."
        except Exception as e:
            return False, "Invalid master password or corrupted vault file."

    def lock_vault(self):
        self.master_password = None
        self.entries = []
        self.is_unlocked = False

    def save_vault(self) -> Tuple[bool, str]:
        if not self.is_unlocked or not self.master_password:
            return False, "Cannot save: vault is locked."

        try:
            plaintext = json.dumps(self.entries, indent=2)
            envelope = VaultCrypto.encrypt(plaintext, self.master_password)
            with open(self.vault_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2)
            return True, "Saved successfully"
        except Exception as e:
            return False, f"Error saving vault: {str(e)}"

    def add_entry(self, service: str, account: str, password: str, notes: str = "", url: str = "") -> Dict[str, Any]:
        entry = {
            "id": f"entry_{int(time.time() * 1000)}",
            "service": service.strip() or "Untitled",
            "account": account.strip(),
            "password": password,
            "url": url.strip(),
            "notes": notes.strip(),
            "created_at": int(time.time()),
            "updated_at": int(time.time())
        }
        self.entries.append(entry)
        self.save_vault()
        return entry

    def update_entry(self, entry_id: str, service: str, account: str, password: str, notes: str = "", url: str = "") -> bool:
        for item in self.entries:
            if item.get("id") == entry_id:
                item["service"] = service.strip() or "Untitled"
                item["account"] = account.strip()
                item["password"] = password
                item["url"] = url.strip()
                item["notes"] = notes.strip()
                item["updated_at"] = int(time.time())
                self.save_vault()
                return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        initial_len = len(self.entries)
        self.entries = [e for e in self.entries if e.get("id") != entry_id]
        if len(self.entries) < initial_len:
            self.save_vault()
            return True
        return False
