import csv
import json
import re
import io
import subprocess
from typing import List, Dict, Any, Tuple, Optional

class PhoneDataScraper:
    """
    Universal Scraper and Importer for Stored Phone Credentials.
    Supports:
      1. Chrome / Samsung Internet / Firefox CSV exports
      2. Bitwarden / Keepass / 1Password / LastPass JSON & CSV exports
      3. Google Passwords CSV
      4. Plain Text / Unstructured lists of accounts & passwords
      5. Direct ADB USB / Wireless Scraper (pulls saved browser exports or app backups if connected)
    """

    @classmethod
    def parse_csv_data(cls, content: str) -> List[Dict[str, str]]:
        """Parses standard CSV exports from Chrome, Google Password Manager, Bitwarden, etc."""
        results = []
        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                # Normalize keys by stripping and lowercasing
                norm_row = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}

                # Service / Name / Title
                service = norm_row.get("name") or norm_row.get("title") or norm_row.get("url") or norm_row.get("service") or ""
                # Clean up domain from URL if URL was used
                if service.startswith("http://") or service.startswith("https://"):
                    domain_match = re.search(r"https?://(?:www\.)?([^/:\?]+)", service)
                    if domain_match:
                        service = domain_match.group(1).capitalize()

                # Username / Account / Email
                account = (
                    norm_row.get("username") or norm_row.get("login_username") or
                    norm_row.get("account") or norm_row.get("email") or norm_row.get("user") or ""
                )

                # Password
                password = (
                    norm_row.get("password") or norm_row.get("login_password") or
                    norm_row.get("pass") or norm_row.get("secret") or ""
                )

                # URL
                url = norm_row.get("url") or norm_row.get("website") or ""

                # Notes
                notes = norm_row.get("notes") or norm_row.get("note") or ""

                if password and password.strip():
                    results.append({
                        "service": service or "Imported Account",
                        "account": account,
                        "password": password,
                        "url": url,
                        "notes": notes
                    })
        except Exception:
            pass
        return results

    @classmethod
    def parse_json_data(cls, content: str) -> List[Dict[str, str]]:
        """Parses Bitwarden / 1Password / Custom JSON exports."""
        results = []
        try:
            data = json.loads(content)
            # Bitwarden format
            if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                for item in data["items"]:
                    name = item.get("name", "Imported")
                    login = item.get("login", {})
                    account = login.get("username", "")
                    password = login.get("password", "")
                    notes = item.get("notes", "")
                    uris = login.get("uris", [])
                    url = uris[0].get("uri", "") if uris else ""
                    if password and password.strip():
                        results.append({
                            "service": name,
                            "account": account,
                            "password": password,
                            "url": url,
                            "notes": notes or ""
                        })
                return results

            # Standard list of dicts
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        service = item.get("service") or item.get("name") or item.get("title") or "Imported"
                        account = item.get("account") or item.get("username") or item.get("email") or ""
                        password = item.get("password") or item.get("pass") or ""
                        url = item.get("url") or ""
                        notes = item.get("notes") or ""
                        if password and password.strip():
                            results.append({
                                "service": service,
                                "account": account,
                                "password": password,
                                "url": url,
                                "notes": notes
                            })
        except Exception:
            pass
        return results

    @classmethod
    def parse_text_dump(cls, text: str) -> List[Dict[str, str]]:
        """Parses plain text dumps, copy-pasted blocks, or unstructured lists."""
        results = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        current_entry = {}
        for line in lines:
            # Check key: value patterns
            m_s = re.match(r"^(?:service|website|site|app|title)[:=\t\s]+(.+)$", line, re.IGNORECASE)
            m_u = re.match(r"^(?:user|username|account|email|login)[:=\t\s]+(.+)$", line, re.IGNORECASE)
            m_p = re.match(r"^(?:pass|password|secret|pin)[:=\t\s]+(.+)$", line, re.IGNORECASE)
            m_url = re.match(r"^(?:url|link)[:=\t\s]+(.+)$", line, re.IGNORECASE)

            if m_s:
                if current_entry.get("password") or current_entry.get("account"):
                    results.append(cls._finalize_entry(current_entry))
                    current_entry = {}
                current_entry["service"] = m_s.group(1).strip()
            elif m_u:
                current_entry["account"] = m_u.group(1).strip()
            elif m_p:
                current_entry["password"] = m_p.group(1).strip()
            elif m_url:
                current_entry["url"] = m_url.group(1).strip()
            elif ":" in line:
                # Potential delimiter format e.g. "service:user:pass" or "user:pass"
                parts = line.split(":")
                if len(parts) == 3:
                    results.append({
                        "service": parts[0].strip(),
                        "account": parts[1].strip(),
                        "password": parts[2].strip(),
                        "url": "",
                        "notes": ""
                    })
                elif len(parts) == 2 and not line.startswith("http"):
                    results.append({
                        "service": "Imported",
                        "account": parts[0].strip(),
                        "password": parts[1].strip(),
                        "url": "",
                        "notes": ""
                    })

        if current_entry.get("password") or current_entry.get("account"):
            results.append(cls._finalize_entry(current_entry))

        return results

    @classmethod
    def _finalize_entry(cls, e: dict) -> dict:
        return {
            "service": e.get("service") or "Imported Account",
            "account": e.get("account", ""),
            "password": e.get("password", ""),
            "url": e.get("url", ""),
            "notes": e.get("notes", "")
        }

    @classmethod
    def scrape_from_string(cls, content: str) -> List[Dict[str, str]]:
        """Auto-detects format (JSON, CSV, or Text Dump) and parses all credentials."""
        cleaned = content.strip()
        if not cleaned:
            return []

        # Try JSON
        if cleaned.startswith("{") or cleaned.startswith("["):
            json_res = cls.parse_json_data(cleaned)
            if json_res:
                return json_res

        # Try CSV
        if "," in cleaned or "\t" in cleaned:
            csv_res = cls.parse_csv_data(cleaned)
            if csv_res and len(csv_res) > 0 and (csv_res[0]["account"] or csv_res[0]["password"]):
                return csv_res

        # Fallback to text dump
        return cls.parse_text_dump(cleaned)

    @classmethod
    def scrape_from_file(cls, file_path: str) -> List[Dict[str, str]]:
        """Reads file from disk and parses stored credentials."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return cls.scrape_from_string(content)

    @classmethod
    def scrape_adb_phone(cls) -> Tuple[bool, List[Dict[str, str]], str]:
        """
        Attempts to scan a connected Android phone via ADB for exported credentials
        in Downloads or Documents folder (e.g. Chrome 'Chrome Passwords.csv', 'passwords.csv', etc.).
        """
        try:
            # Check devices
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
            lines = [l for l in res.stdout.strip().splitlines()[1:] if l.strip() and not l.startswith("*")]
            if not lines:
                return False, [], "No Android phone connected via USB / Wi-Fi ADB. Please enable USB Debugging or select an export file."

            device_id = lines[0].split()[0]

            # Look for common password export files on phone storage
            find_cmd = [
                "adb", "-s", device_id, "shell",
                "find /sdcard/Download /sdcard/Documents -iname '*pass*' -o -iname '*export*' 2>/dev/null"
            ]
            find_res = subprocess.run(find_cmd, capture_output=True, text=True, timeout=5)
            candidate_files = [f.strip() for f in find_res.stdout.splitlines() if f.strip() and any(f.endswith(ext) for ext in [".csv", ".json", ".txt"])]

            all_creds = []
            import tempfile, os, urllib.request, urllib.parse

            if candidate_files:
                for remote_file in candidate_files[:5]:
                    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
                        tmp_path = tmp.name
                    try:
                        subprocess.run(["adb", "-s", device_id, "pull", remote_file, tmp_path], capture_output=True, timeout=5)
                        creds = cls.scrape_from_file(tmp_path)
                        all_creds.extend(creds)
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)

            # Also inspect live open tabs from Chrome DevTools Remote Debugging
            try:
                dt_port = 9338
                dt_fwd = subprocess.run(["adb", "-s", device_id, "forward", f"tcp:{dt_port}", "localabstract:chrome_devtools_remote"], capture_output=True, text=True, timeout=3)
                if dt_fwd.returncode == 0:
                    try:
                        req = urllib.request.Request(f"http://127.0.0.1:{dt_port}/json", headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            pages = json.loads(resp.read().decode())
                            for p in pages:
                                u = p.get("url", "")
                                t = p.get("title", "")
                                if not u or u.startswith("chrome://") or u.startswith("about:"):
                                    continue
                                d_match = re.search(r"https?://(?:www\.)?([^/:\?]+)", u)
                                s_name = d_match.group(1).capitalize() if d_match else t
                                e_match = re.search(r"[?&](?:Email|username|user|login)=([^&]+)", u, re.IGNORECASE)
                                acc = urllib.parse.unquote(e_match.group(1)) if e_match else ""
                                all_creds.append({
                                    "service": s_name,
                                    "account": acc,
                                    "password": "",
                                    "url": u,
                                    "notes": f"Scraped from open mobile browser tab: {t}"
                                })
                    finally:
                        subprocess.run(["adb", "-s", device_id, "forward", "--remove", f"tcp:{dt_port}"], capture_output=True)
            except Exception:
                pass

            if not all_creds:
                return False, [], f"Connected to device {device_id}, but no exported password files or active browser tabs found. Export passwords from your mobile browser into Downloads first."

            return True, all_creds, f"Scraped {len(all_creds)} credentials and browser entries directly from phone ({device_id})!"
        except Exception as e:
            return False, [], f"ADB scrape error: {str(e)}"

    @classmethod
    def scrape_desktop_browsers(cls) -> Tuple[bool, List[Dict[str, str]], str]:
        """
        Scrapes credentials directly from installed desktop browsers:
        - Chromium, Google Chrome, Brave, Edge, and other Chromium-based browsers
        - Decrypts stored logins using Linux DPAPI/AES-128-CBC standard key
        """
        import os, glob, sqlite3, shutil, tempfile
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            has_crypto = True
        except ImportError:
            has_crypto = False

        results = []
        home = os.path.expanduser("~")
        
        # Chromium search paths (native, snap, flatpak)
        candidate_paths = [
            f"{home}/.config/google-chrome/Default/Login Data",
            f"{home}/.config/google-chrome/Profile */Login Data",
            f"{home}/.config/chromium/Default/Login Data",
            f"{home}/.config/chromium/Profile */Login Data",
            f"{home}/.config/BraveSoftware/Brave-Browser/Default/Login Data",
            f"{home}/.config/BraveSoftware/Brave-Browser/Profile */Login Data",
            f"{home}/.config/microsoft-edge/Default/Login Data",
            f"{home}/.var/app/org.chromium.Chromium/config/chromium/Default/Login Data",
            f"{home}/snap/brave/*/.config/BraveSoftware/Brave-Browser/Default/Login Data",
            f"{home}/snap/chromium/*/.config/chromium/Default/Login Data",
            f"{home}/.config/google-voice-chromium/Default/Login Data",
        ]

        found_db_files = []
        for pat in candidate_paths:
            found_db_files.extend(glob.glob(pat))

        # Remove duplicates
        found_db_files = list(set(found_db_files))

        def decrypt_chromium_pass(enc_bytes):
            if not enc_bytes or not has_crypto:
                return ""
            if not enc_bytes.startswith(b"v10") and not enc_bytes.startswith(b"v11"):
                try:
                    return enc_bytes.decode("utf-8")
                except Exception:
                    return ""
            
            # Linux Chromium uses PBKDF2 with salt 'saltysalt', 1 iteration, password 'peanuts'
            try:
                kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=16, salt=b"saltysalt", iterations=1)
                key = kdf.derive(b"peanuts")
                cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16))
                dec = cipher.decryptor().update(enc_bytes[3:]) + cipher.decryptor().finalize()
                pad_len = dec[-1]
                if 1 <= pad_len <= 16:
                    return dec[:-pad_len].decode("utf-8", errors="replace")
                return dec.decode("utf-8", errors="replace")
            except Exception:
                return ""

        for db_path in found_db_files:
            if not os.path.exists(db_path):
                continue
            
            # Copy SQLite DB to temp to avoid lock contention if browser is running
            with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
                tmp_db = tmp.name
            
            try:
                shutil.copy2(db_path, tmp_db)
                conn = sqlite3.connect(tmp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                rows = cursor.fetchall()
                conn.close()

                # Infer browser name
                browser_name = "Desktop Browser"
                if "brave" in db_path.lower():
                    browser_name = "Brave"
                elif "chrome" in db_path.lower():
                    browser_name = "Chrome"
                elif "chromium" in db_path.lower():
                    browser_name = "Chromium"
                elif "edge" in db_path.lower():
                    browser_name = "Edge"

                for origin_url, username, pass_blob in rows:
                    if not pass_blob:
                        continue
                    
                    plain_pass = decrypt_chromium_pass(pass_blob)
                    if not plain_pass or not plain_pass.strip():
                        continue

                    # Extract domain for service name
                    d_match = re.search(r"https?://(?:www\.)?([^/:\?]+)", origin_url or "")
                    service_name = d_match.group(1).capitalize() if d_match else browser_name

                    results.append({
                        "service": service_name,
                        "account": username or "",
                        "password": plain_pass,
                        "url": origin_url or "",
                        "notes": f"Scraped from {browser_name} database ({os.path.basename(os.path.dirname(db_path))})"
                    })
            except Exception:
                pass
            finally:
                if os.path.exists(tmp_db):
                    os.unlink(tmp_db)

        # Also search Downloads, Documents, Desktop for exported password files
        search_dirs = [f"{home}/Downloads", f"{home}/Documents", f"{home}/Desktop", home]
        for sdir in search_dirs:
            if os.path.exists(sdir):
                for fname in os.listdir(sdir):
                    fpath = os.path.join(sdir, fname)
                    if os.path.isfile(fpath) and any(fname.lower().endswith(ext) for ext in [".csv", ".json"]):
                        if any(k in fname.lower() for k in ["pass", "login", "export", "credential"]):
                            try:
                                file_creds = cls.scrape_from_file(fpath)
                                for fc in file_creds:
                                    if fc.get("password") and fc["password"].strip():
                                        results.append(fc)
                            except Exception:
                                pass

        # Deduplicate and ensure only entries WITH passwords remain
        valid_results = []
        seen = set()
        for r in results:
            pw = r.get("password", "").strip()
            if not pw:
                continue
            key = (r.get("service", "").lower(), r.get("account", "").lower(), pw)
            if key not in seen:
                seen.add(key)
                valid_results.append(r)

        if not valid_results:
            return False, [], "No credentials with saved passwords found in desktop browsers or computer files."

        return True, valid_results, f"Scraped {len(valid_results)} credentials with passwords directly from local computer!"



