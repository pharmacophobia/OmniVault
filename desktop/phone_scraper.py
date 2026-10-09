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

                if service or account or password:
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
                    if account or password:
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
                        if account or password:
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

            if not candidate_files:
                return False, [], f"Connected to device {device_id}, but no exported password files (.csv, .json) found in Downloads or Documents folder. Export your passwords from Chrome/Browser to Downloads on your phone first."

            all_creds = []
            import tempfile, os
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

            return True, all_creds, f"Scraped {len(all_creds)} credentials directly from {len(candidate_files)} file(s) on your phone!"
        except Exception as e:
            return False, [], f"ADB scrape error: {str(e)}"
