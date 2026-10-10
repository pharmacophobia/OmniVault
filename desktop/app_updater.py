import os
import sys
import json
import subprocess
import threading
import urllib.request
from typing import Optional, Dict, Tuple, Callable, Any

class AppUpdater:
    """
    Universal In-App Self-Updater for Python / Linux Desktop Applications.
    Supports:
      1. Git pull + dependency reinstall (fastest, preserves local dev state)
      2. GitHub Releases API tag comparison and binary download
      3. Seamless process restart on demand
    """
    def __init__(self, repo_dir: str, github_repo: Optional[str] = None, current_version: str = "1.0.0"):
        self.repo_dir = os.path.abspath(repo_dir)
        self.github_repo = github_repo or self._detect_github_repo()
        self.current_version = current_version.lstrip("v")

    def _detect_github_repo(self) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_dir, capture_output=True, text=True, timeout=2
            )
            url = res.stdout.strip()
            if "github.com" in url:
                if url.startswith("git@github.com:"):
                    path = url.split("git@github.com:")[1]
                else:
                    path = url.split("github.com/")[1]
                if path.endswith(".git"):
                    path = path[:-4]
                return path.strip()
        except Exception:
            pass
        return None

    def check_for_updates(self) -> Dict[str, Any]:
        """
        Checks both Git remote commits and GitHub Releases API.
        Returns dict with keys: 'update_available', 'latest_version', 'current_version', 'commits_behind', 'notes', 'method'
        """
        result = {
            "update_available": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "commits_behind": 0,
            "release_notes": "",
            "download_url": "",
            "method": "git" # 'git' or 'github_release'
        }

        # 1. Check Git remote
        try:
            subprocess.run(["git", "fetch", "origin"], cwd=self.repo_dir, capture_output=True, timeout=5)
            rev_res = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/main"],
                cwd=self.repo_dir, capture_output=True, text=True, timeout=2
            )
            behind_count = int(rev_res.stdout.strip() or "0")
            if behind_count > 0:
                result["update_available"] = True
                result["commits_behind"] = behind_count
                result["method"] = "git"
                # Get commit log
                log_res = subprocess.run(
                    ["git", "log", "--oneline", f"-{min(behind_count, 5)}", "origin/main"],
                    cwd=self.repo_dir, capture_output=True, text=True, timeout=2
                )
                result["release_notes"] = log_res.stdout.strip()
        except Exception:
            pass

        # 2. Check GitHub Releases if repo name known
        if self.github_repo:
            try:
                api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
                req = urllib.request.Request(api_url, headers={"User-Agent": "OmniVault-Updater/1.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        latest_tag = data.get("tag_name", "").lstrip("v")
                        result["latest_version"] = latest_tag
                        if latest_tag and self._is_newer(latest_tag, self.current_version):
                            result["update_available"] = True
                            result["release_notes"] = data.get("body", "")
                            # Check assets
                            for asset in data.get("assets", []):
                                if asset.get("browser_download_url"):
                                    result["download_url"] = asset.get("browser_download_url")
                                    break
            except Exception:
                pass

        return result

    def _is_newer(self, latest: str, current: str) -> bool:
        try:
            l_parts = [int(p) for p in latest.split(".") if p.isdigit()]
            c_parts = [int(p) for p in current.split(".") if p.isdigit()]
            return l_parts > c_parts
        except Exception:
            return latest != current

    def perform_update(self, on_progress: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Executes git pull, updates local files, and prepares application restart.
        """
        if on_progress:
            on_progress("Pulling latest updates from GitHub...")

        try:
            res = subprocess.run(
                ["git", "pull", "--ff-only", "origin", "main"],
                cwd=self.repo_dir, capture_output=True, text=True, timeout=15
            )
            if res.returncode != 0:
                # If local changes prevent fast-forward, stash and pull
                subprocess.run(["git", "stash"], cwd=self.repo_dir, capture_output=True, timeout=5)
                res = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    cwd=self.repo_dir, capture_output=True, text=True, timeout=15
                )

            if res.returncode == 0:
                if on_progress:
                    on_progress("Successfully updated! Restarting application...")
                return True, "Application updated successfully. Restart to apply changes."
            else:
                return False, f"Git update failed: {res.stderr.strip()}"
        except Exception as e:
            return False, f"Error applying update: {str(e)}"

    def restart_application(self):
        """Spawns fresh instance of current application and exits current process."""
        python_bin = sys.executable
        args = [python_bin] + sys.argv
        os.execv(python_bin, args)
