import sys
import os
import json
import base64
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFileDialog, QSplitter,
    QTextEdit, QProgressBar, QCheckBox, QSpinBox, QGroupBox, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QColor, QAction

from vault_manager import VaultManager
from password_gen import PasswordGenerator
from sync_server import SyncServer

class VisionWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, vision_extractor, image_path: str):
        super().__init__()
        self.vision_extractor = vision_extractor
        self.image_path = image_path

    def run(self):
        try:
            result = self.vision_extractor.extract_from_image(self.image_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class EntryDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Account Entry" if entry else "Add New Account Entry")
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel { color: #cdd6f4; font-weight: bold; }
            QLineEdit, QTextEdit { background-color: #313244; color: #ffffff; border: 1px solid #45475a; border-radius: 6px; padding: 8px; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px; padding: 8px 16px; }
            QPushButton:hover { background-color: #b4befe; }
        """)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Service / Website:"))
        self.service_input = QLineEdit()
        layout.addWidget(self.service_input)

        layout.addWidget(QLabel("Account Name / Email / Username:"))
        self.account_input = QLineEdit()
        layout.addWidget(self.account_input)

        pass_label_layout = QHBoxLayout()
        pass_label_layout.addWidget(QLabel("Password:"))
        self.gen_btn = QPushButton("🎲 Generate Secure")
        self.gen_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-size: 11px; padding: 4px 8px;")
        self.gen_btn.clicked.connect(self._generate_password)
        pass_label_layout.addWidget(self.gen_btn)
        layout.addLayout(pass_label_layout)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        layout.addWidget(self.password_input)

        layout.addWidget(QLabel("URL (Optional):"))
        self.url_input = QLineEdit()
        layout.addWidget(self.url_input)

        layout.addWidget(QLabel("Notes (Optional):"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        layout.addWidget(self.notes_input)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Entry")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        if self.entry:
            self.service_input.setText(self.entry.get("service", ""))
            self.account_input.setText(self.entry.get("account", ""))
            self.password_input.setText(self.entry.get("password", ""))
            self.url_input.setText(self.entry.get("url", ""))
            self.notes_input.setPlainText(self.entry.get("notes", ""))

    def _generate_password(self):
        pw = PasswordGenerator.generate(18)
        self.password_input.setText(pw)

    def get_data(self):
        return {
            "service": self.service_input.text().strip(),
            "account": self.account_input.text().strip(),
            "password": self.password_input.text(),
            "url": self.url_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip()
        }

class PasswordGenDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Password Generator")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel { color: #cdd6f4; font-size: 13px; }
            QLineEdit { background-color: #313244; color: #a6e3a1; font-family: monospace; font-size: 16px; border: 1px solid #45475a; border-radius: 6px; padding: 8px; font-weight: bold; }
            QCheckBox { color: #cdd6f4; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px; padding: 8px 16px; }
        """)

        layout = QVBoxLayout(self)

        self.result_display = QLineEdit()
        self.result_display.setReadOnly(True)
        layout.addWidget(self.result_display)

        self.strength_label = QLabel("Strength: -")
        layout.addWidget(self.strength_label)

        # Options
        opt_group = QGroupBox("Rules")
        opt_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cdd6f4; }")
        opt_layout = QVBoxLayout(opt_group)

        len_layout = QHBoxLayout()
        len_layout.addWidget(QLabel("Length:"))
        self.len_spin = QSpinBox()
        self.len_spin.setRange(8, 64)
        self.len_spin.setValue(18)
        self.len_spin.setStyleSheet("background-color: #313244; color: #ffffff; padding: 4px;")
        self.len_spin.valueChanged.connect(self._regenerate)
        len_layout.addWidget(self.len_spin)
        opt_layout.addLayout(len_layout)

        self.chk_upper = QCheckBox("Uppercase (A-Z)")
        self.chk_upper.setChecked(True)
        self.chk_upper.stateChanged.connect(self._regenerate)
        opt_layout.addWidget(self.chk_upper)

        self.chk_lower = QCheckBox("Lowercase (a-z)")
        self.chk_lower.setChecked(True)
        self.chk_lower.stateChanged.connect(self._regenerate)
        opt_layout.addWidget(self.chk_lower)

        self.chk_digits = QCheckBox("Numbers (0-9)")
        self.chk_digits.setChecked(True)
        self.chk_digits.stateChanged.connect(self._regenerate)
        opt_layout.addWidget(self.chk_digits)

        self.chk_symbols = QCheckBox("Symbols (!@#$%^&*)")
        self.chk_symbols.setChecked(True)
        self.chk_symbols.stateChanged.connect(self._regenerate)
        opt_layout.addWidget(self.chk_symbols)

        layout.addWidget(opt_group)

        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Re-roll")
        self.refresh_btn.clicked.connect(self._regenerate)
        btn_layout.addWidget(self.refresh_btn)

        self.copy_btn = QPushButton("📋 Copy Password")
        self.copy_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        self.copy_btn.clicked.connect(self._copy_password)
        btn_layout.addWidget(self.copy_btn)

        layout.addLayout(btn_layout)
        self._regenerate()

    def _regenerate(self):
        pw = PasswordGenerator.generate(
            length=self.len_spin.value(),
            use_upper=self.chk_upper.isChecked(),
            use_lower=self.chk_lower.isChecked(),
            use_digits=self.chk_digits.isChecked(),
            use_symbols=self.chk_symbols.isChecked()
        )
        self.result_display.setText(pw)
        strength = PasswordGenerator.calculate_strength(pw)
        self.strength_label.setText(f"Strength: {strength['label']}")
        self.strength_label.setStyleSheet(f"color: {strength['color']}; font-weight: bold;")

    def _copy_password(self):
        QApplication.clipboard().setText(self.result_display.text())
        QMessageBox.information(self, "Copied", "Password copied to clipboard!")

class PhoneScraperDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📥 Phone Data Scraper & Importer")
        self.setMinimumWidth(550)
        self.setMinimumHeight(450)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel { color: #cdd6f4; font-size: 13px; }
            QTextEdit { background-color: #313244; color: #ffffff; font-family: monospace; border: 1px solid #45475a; border-radius: 6px; padding: 8px; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px; padding: 8px 14px; }
        """)

        layout = QVBoxLayout(self)

        title = QLabel("📥 Import Stored Credentials from Phone")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #cba6f7;")
        layout.addWidget(title)

        desc = QLabel(
            "Import passwords exported from Chrome, Samsung Internet, Firefox, Bitwarden, or 1Password on your phone.\n"
            "Choose a method below:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self.file_btn = QPushButton("📁 File (CSV/JSON)")
        self.file_btn.clicked.connect(self._select_file)
        btn_row.addWidget(self.file_btn)

        self.desktop_browser_btn = QPushButton("💻 Scrape Desktop Browsers")
        self.desktop_browser_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        self.desktop_browser_btn.clicked.connect(self._scan_desktop_browsers)
        btn_row.addWidget(self.desktop_browser_btn)

        self.adb_btn = QPushButton("🔌 Auto-Scan Phone (ADB)")
        self.adb_btn.setStyleSheet("background-color: #fab387; color: #11111b; font-weight: bold;")
        self.adb_btn.clicked.connect(self._scan_adb)
        btn_row.addWidget(self.adb_btn)

        self.browser_btn = QPushButton("🌐 Scrape Phone Chrome Tabs")
        self.browser_btn.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold;")
        self.browser_btn.clicked.connect(self._scan_browser_tabs)
        btn_row.addWidget(self.browser_btn)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("Or Paste Raw Export / Text Dump Here:"))
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Paste CSV, JSON, or list of 'Website, username, password'...")
        layout.addWidget(self.text_input)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        layout.addWidget(self.status_label)

        action_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        self.cancel_btn.clicked.connect(self.reject)
        action_row.addWidget(self.cancel_btn)

        self.import_btn = QPushButton("Parse & Import to Vault")
        self.import_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b;")
        self.import_btn.clicked.connect(self._do_import)
        action_row.addWidget(self.import_btn)

        layout.addLayout(action_row)
        self.scraped_entries = []

    def _scan_desktop_browsers(self):
        self.status_label.setText("Scanning local desktop browsers (Brave, Chrome, Chromium, Edge)...")
        from phone_scraper import PhoneDataScraper
        ok, entries, msg = PhoneDataScraper.scrape_desktop_browsers()
        if ok and entries:
            self.scraped_entries = entries
            self.status_label.setText(msg)
            preview = f"# Found {len(entries)} credentials across desktop browsers:\n"
            for e in entries[:15]:
                pw_preview = "***" if e.get("password") else "(No saved password)"
                preview += f"- [{e['service']}] {e['account']} : {pw_preview} ({e['url']})\n"
            if len(entries) > 15:
                preview += f"...and {len(entries) - 15} more.\n"
            self.text_input.setPlainText(preview)
        else:
            QMessageBox.information(self, "Browser Scrape", msg)
            self.status_label.setText("No browser credentials found. Export them from browser settings if needed.")

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Password Export File", "", "Supported Files (*.csv *.json *.txt);;All Files (*)"
        )
        if not file_path:
            return
        from phone_scraper import PhoneDataScraper
        self.scraped_entries = PhoneDataScraper.scrape_from_file(file_path)
        self.status_label.setText(f"Loaded file: Parsed {len(self.scraped_entries)} credentials ready to import!")
        self.text_input.setPlainText(f"# Loaded from {file_path}:\n# Found {len(self.scraped_entries)} account entries.")

    def _scan_adb(self):
        self.status_label.setText("Scanning phone via ADB for exported credentials...")
        from phone_scraper import PhoneDataScraper
        ok, entries, msg = PhoneDataScraper.scrape_adb_phone()
        if ok and entries:
            self.scraped_entries = entries
            self.status_label.setText(msg)
            self.text_input.setPlainText(f"# Found {len(entries)} credentials and tabs from connected phone!")
        else:
            QMessageBox.information(self, "Phone Scan", msg)
            self.status_label.setText("No exported files found via ADB. Export to Downloads or pick file manually.")

    def _scan_browser_tabs(self):
        self.status_label.setText("Connecting to Android Chrome via DevTools...")
        import subprocess, json, re, urllib.request, urllib.parse
        port = 9339
        try:
            fwd = subprocess.run(["adb", "forward", f"tcp:{port}", "localabstract:chrome_devtools_remote"], capture_output=True, text=True, timeout=3)
            if fwd.returncode != 0:
                QMessageBox.warning(self, "Browser Scrape", "Failed to connect to mobile Chrome. Make sure Chrome is open on your phone and USB Debugging is authorized.")
                return

            req = urllib.request.Request(f"http://127.0.0.1:{port}/json", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                pages = json.loads(resp.read().decode())

            tab_entries = []
            for p in pages:
                u = p.get("url", "")
                t = p.get("title", "")
                if not u or u.startswith("chrome://") or u.startswith("about:"):
                    continue
                d_match = re.search(r"https?://(?:www\.)?([^/:\?]+)", u)
                s_name = d_match.group(1).capitalize() if d_match else t
                e_match = re.search(r"[?&](?:Email|username|user|login)=([^&]+)", u, re.IGNORECASE)
                acc = urllib.parse.unquote(e_match.group(1)) if e_match else ""
                tab_entries.append({
                    "service": s_name,
                    "account": acc,
                    "password": "",
                    "url": u,
                    "notes": f"Scraped from open mobile browser tab: {t}"
                })

            if tab_entries:
                self.scraped_entries = tab_entries
                self.status_label.setText(f"Successfully scraped {len(tab_entries)} open sites/accounts from Android Chrome!")
                self.text_input.setPlainText(f"# Scraped {len(tab_entries)} sites from open phone browser tabs:\n" + "\n".join([f"- {e['service']} ({e['account']}): {e['url']}" for e in tab_entries[:15]]) + f"\n...and {len(tab_entries)-15} more.")
            else:
                QMessageBox.information(self, "Browser Scrape", "Connected to Chrome, but no open website tabs were found.")
        except Exception as e:
            QMessageBox.critical(self, "Browser Scrape Error", f"Error scraping phone browser tabs: {e}")
        finally:
            subprocess.run(["adb", "forward", "--remove", f"tcp:{port}"], capture_output=True)

    def _do_import(self):
        if not self.scraped_entries:
            text = self.text_input.toPlainText().strip()
            if text and not text.startswith("#"):
                from phone_scraper import PhoneDataScraper
                self.scraped_entries = PhoneDataScraper.scrape_from_string(text)

        if not self.scraped_entries:
            QMessageBox.warning(self, "No Credentials", "No valid credentials found to import.")
            return

        self.accept()

    def get_entries(self):
        return self.scraped_entries

class OmniVaultApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.vault_manager = VaultManager()
        self.sync_server = SyncServer(self.vault_manager, port=8765)
        self.sync_server.start()

        self.setWindowTitle("OmniVault - Secure Password Manager")
        self.resize(1000, 680)

        self.setStyleSheet("""
            QMainWindow { background-color: #181825; }
            QWidget { background-color: #181825; color: #cdd6f4; font-family: 'Segoe UI', Arial, sans-serif; }
            QTableWidget { background-color: #1e1e2e; border: 1px solid #313244; gridline-color: #313244; selection-background-color: #45475a; }
            QHeaderView::section { background-color: #11111b; color: #cdd6f4; font-weight: bold; border: 1px solid #313244; padding: 6px; }
            QLineEdit { background-color: #1e1e2e; color: #ffffff; border: 1px solid #45475a; border-radius: 6px; padding: 6px 12px; }
            QPushButton { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 6px 14px; font-weight: bold; }
            QPushButton:hover { background-color: #45475a; color: #ffffff; }
        """)

        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("🔐 OmniVault")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #89b4fa;")
        header_layout.addWidget(title_label)

        self.status_badge = QLabel("🔒 LOCKED")
        self.status_badge.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        self.pico_badge = QLabel("⚡ Pico Typer: Checking...")
        self.pico_badge.setStyleSheet("background-color: #313244; color: #a6e3a1; font-weight: bold; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        header_layout.addWidget(self.pico_badge)

        self.network_label = QLabel(f"📡 Sync Server: 0.0.0.0:8765")
        self.network_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        header_layout.addWidget(self.network_label)

        main_layout.addLayout(header_layout)

        # Auth banner (if locked)
        self.auth_widget = QWidget()
        auth_layout = QHBoxLayout(self.auth_widget)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        self.master_pass_input = QLineEdit()
        self.master_pass_input.setPlaceholderText("Enter Master Password to Unlock or Create Vault...")
        self.master_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_pass_input.returnPressed.connect(self._handle_unlock_or_create)
        auth_layout.addWidget(self.master_pass_input)

        self.unlock_btn = QPushButton("Unlock Vault")
        self.unlock_btn.setStyleSheet("background-color: #89b4fa; color: #11111b;")
        self.unlock_btn.clicked.connect(self._handle_unlock_or_create)
        auth_layout.addWidget(self.unlock_btn)

        self.lock_btn = QPushButton("Lock Vault")
        self.lock_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        self.lock_btn.clicked.connect(self._handle_lock)
        self.lock_btn.setVisible(False)
        auth_layout.addWidget(self.lock_btn)

        main_layout.addWidget(self.auth_widget)

        # Action Toolbar
        self.toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search accounts, services, emails...")
        self.search_input.textChanged.connect(self._render_entries)
        toolbar_layout.addWidget(self.search_input)

        self.add_btn = QPushButton("➕ Add Entry")
        self.add_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b;")
        self.add_btn.clicked.connect(self._add_entry_dialog)
        toolbar_layout.addWidget(self.add_btn)

        self.screenshot_btn = QPushButton("📸 Import Screenshot (AI Vision)")
        self.screenshot_btn.setStyleSheet("background-color: #fab387; color: #11111b;")
        self.screenshot_btn.clicked.connect(self._import_screenshot_dialog)
        toolbar_layout.addWidget(self.screenshot_btn)

        self.pico_sync_btn = QPushButton("⚡ Sync to Pico Flash")
        self.pico_sync_btn.setStyleSheet("background-color: #f9e2af; color: #11111b;")
        self.pico_sync_btn.setToolTip("Upload top vault passwords into Pico 2W Flash memory for standalone keyboard typing")
        self.pico_sync_btn.clicked.connect(self._sync_to_pico_flash)
        toolbar_layout.addWidget(self.pico_sync_btn)

        self.scraper_btn = QPushButton("📥 Scrape Phone Info")
        self.scraper_btn.setStyleSheet("background-color: #cba6f7; color: #11111b; font-weight: bold;")
        self.scraper_btn.setToolTip("Import credentials from Phone browser exports (Chrome, Firefox, Bitwarden, CSV, JSON, ADB)")
        self.scraper_btn.clicked.connect(self._open_phone_scraper_dialog)
        toolbar_layout.addWidget(self.scraper_btn)

        self.pw_gen_btn = QPushButton("🎲 Gen Password")
        self.pw_gen_btn.clicked.connect(self._open_pw_gen)
        toolbar_layout.addWidget(self.pw_gen_btn)

        self.update_btn = QPushButton("🔄 Updates")
        self.update_btn.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold;")
        self.update_btn.setToolTip("Check for updates from GitHub and update OmniVault directly from inside the app")
        self.update_btn.clicked.connect(self._open_updater_dialog)
        toolbar_layout.addWidget(self.update_btn)

        main_layout.addWidget(self.toolbar_widget)
        self.toolbar_widget.setEnabled(False)

        # Status / Vision progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #313244; color: #ffffff; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #89b4fa; }")
        main_layout.addWidget(self.progress_bar)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Service", "Account / Username", "Password", "Updated", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_table_double_click)
        main_layout.addWidget(self.table)

    def _handle_unlock_or_create(self):
        pw = self.master_pass_input.text()
        if not pw:
            QMessageBox.warning(self, "Master Password Required", "Please enter a master password.")
            return

        if not self.vault_manager.has_vault_file():
            # Prompt user to create new vault
            reply = QMessageBox.question(
                self, "Create New Vault?",
                "No encrypted vault found. Would you like to create a new vault with this master password?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                ok, msg = self.vault_manager.create_new_vault(pw)
                if ok:
                    QMessageBox.information(self, "Success", "Vault created and initialized!")
                    self._on_unlocked()
                else:
                    QMessageBox.critical(self, "Error", msg)
            return

        # Attempt unlock
        ok, msg = self.vault_manager.unlock_vault(pw)
        if ok:
            self._on_unlocked()
        else:
            QMessageBox.critical(self, "Unlock Failed", msg)

    def _on_unlocked(self):
        self.status_badge.setText("🔓 UNLOCKED")
        self.status_badge.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
        self.master_pass_input.setVisible(False)
        self.unlock_btn.setVisible(False)
        self.lock_btn.setVisible(True)
        self.toolbar_widget.setEnabled(True)
        self._refresh_pico_status()
        self._render_entries()

    def _handle_lock(self):
        self.vault_manager.lock_vault()
        self.status_badge.setText("🔒 LOCKED")
        self.status_badge.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
        self.master_pass_input.clear()
        self.master_pass_input.setVisible(True)
        self.unlock_btn.setVisible(True)
        self.lock_btn.setVisible(False)
        self.toolbar_widget.setEnabled(False)
        self.table.setRowCount(0)

    def _render_entries(self):
        if not self.vault_manager.is_unlocked:
            return

        query = self.search_input.text().lower().strip()
        filtered = [
            e for e in self.vault_manager.entries
            if query in e.get("service", "").lower() or query in e.get("account", "").lower() or query in e.get("notes", "").lower()
        ]

        self.table.setRowCount(len(filtered))
        for row, entry in enumerate(filtered):
            # Service
            s_item = QTableWidgetItem(entry.get("service", ""))
            s_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            self.table.setItem(row, 0, s_item)

            # Account
            a_item = QTableWidgetItem(entry.get("account", ""))
            self.table.setItem(row, 1, a_item)

            # Password (masked display with copy button)
            p_item = QTableWidgetItem("••••••••••••")
            p_item.setForeground(QColor("#a6adc8"))
            self.table.setItem(row, 2, p_item)

            # Updated
            import datetime
            up_time = datetime.datetime.fromtimestamp(entry.get("updated_at", 0)).strftime("%Y-%m-%d %H:%M")
            self.table.setItem(row, 3, QTableWidgetItem(up_time))

            # Action Buttons widget
            btn_container = QWidget()
            b_layout = QHBoxLayout(btn_container)
            b_layout.setContentsMargins(2, 2, 2, 2)
            b_layout.setSpacing(4)

            copy_acc_btn = QPushButton("📋 Acc")
            copy_acc_btn.setToolTip("Copy Account / Username")
            copy_acc_btn.clicked.connect(lambda _, a=entry.get("account", ""): self._copy_to_clipboard(a, "Account"))
            b_layout.addWidget(copy_acc_btn)

            copy_pw_btn = QPushButton("🔑 Pass")
            copy_pw_btn.setToolTip("Copy Password to clipboard")
            copy_pw_btn.setStyleSheet("background-color: #89b4fa; color: #11111b;")
            copy_pw_btn.clicked.connect(lambda _, p=entry.get("password", ""): self._copy_to_clipboard(p, "Password"))
            b_layout.addWidget(copy_pw_btn)

            pico_type_btn = QPushButton("⚡ Type")
            pico_type_btn.setToolTip("Type password directly into active PC cursor via Pico USB HID keyboard")
            pico_type_btn.setStyleSheet("background-color: #fab387; color: #11111b; font-weight: bold;")
            pico_type_btn.clicked.connect(lambda _, e=entry: self._type_via_pico(e))
            b_layout.addWidget(pico_type_btn)

            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Edit Entry")
            edit_btn.clicked.connect(lambda _, e=entry: self._edit_entry_dialog(e))
            b_layout.addWidget(edit_btn)

            del_btn = QPushButton("🗑️")
            del_btn.setToolTip("Delete Entry")
            del_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
            del_btn.clicked.connect(lambda _, eid=entry.get("id"): self._delete_entry(eid))
            b_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 4, btn_container)

    def _copy_to_clipboard(self, text: str, name: str):
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(f"Copied {name} to clipboard!", 2500)

    def _add_entry_dialog(self, initial_data=None):
        dialog = EntryDialog(self, entry=initial_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["service"] and not data["account"]:
                QMessageBox.warning(self, "Invalid Entry", "Please provide at least a service name or account.")
                return
            self.vault_manager.add_entry(
                service=data["service"],
                account=data["account"],
                password=data["password"],
                notes=data["notes"],
                url=data["url"]
            )
            self._render_entries()

    def _edit_entry_dialog(self, entry):
        dialog = EntryDialog(self, entry=entry)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.vault_manager.update_entry(
                entry_id=entry["id"],
                service=data["service"],
                account=data["account"],
                password=data["password"],
                notes=data["notes"],
                url=data["url"]
            )
            self._render_entries()

    def _on_table_double_click(self, index):
        row = index.row()
        query = self.search_input.text().lower().strip()
        filtered = [
            e for e in self.vault_manager.entries
            if query in e.get("service", "").lower() or query in e.get("account", "").lower() or query in e.get("notes", "").lower()
        ]
        if 0 <= row < len(filtered):
            self._edit_entry_dialog(filtered[row])

    def _delete_entry(self, entry_id):
        reply = QMessageBox.question(
            self, "Confirm Delete", "Are you sure you want to permanently delete this credential?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.vault_manager.delete_entry(entry_id)
            self._render_entries()

    def _open_pw_gen(self):
        dlg = PasswordGenDialog(self)
        dlg.exec()

    def _open_phone_scraper_dialog(self):
        dlg = PhoneScraperDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entries = dlg.get_entries()
            added = 0
            for item in entries:
                self.vault_manager.add_entry(
                    service=item.get("service", "Imported"),
                    account=item.get("account", ""),
                    password=item.get("password", ""),
                    url=item.get("url", ""),
                    notes=item.get("notes", "")
                )
                added += 1
            self._render_entries()
            QMessageBox.information(
                self, "Import Successful",
                f"Successfully imported {added} credentials from your phone into OmniVault!"
            )

    def _open_updater_dialog(self):
        from update_dialog import UpdateDialog
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dlg = UpdateDialog(self, repo_dir=repo_root, app_name="OmniVault", current_version="1.0.0")
        dlg.exec()

    def _import_screenshot_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Screenshot of Credentials", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_path:
            return

        self.progress_bar.setVisible(True)
        self.screenshot_btn.setEnabled(False)
        self.statusBar().showMessage("Extracting credentials with local Ollama vision model (llama3.2-vision)...")

        self.worker = VisionWorker(self.vault_manager.vision_extractor, file_path)
        self.worker.finished.connect(self._on_vision_finished)
        self.worker.error.connect(self._on_vision_error)
        self.worker.start()

    def _on_vision_finished(self, result: dict):
        self.progress_bar.setVisible(False)
        self.screenshot_btn.setEnabled(True)
        self.statusBar().showMessage("Vision model extraction complete!", 4000)

        # Open EntryDialog prefilled with extracted credentials
        self._add_entry_dialog(initial_data=result)

    def _on_vision_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.screenshot_btn.setEnabled(True)
        QMessageBox.critical(self, "Vision Extraction Error", f"Failed to extract credentials from image:\n{err_msg}")

    def _type_via_pico(self, entry: dict):
        pwd = entry.get("password", "")
        service = entry.get("service", "Account")
        if not pwd:
            QMessageBox.warning(self, "No Password", "This entry does not have a password to type.")
            return

        bridge = self.vault_manager.pico_bridge
        if not bridge.is_connected_serial():
            ok, msg = bridge.connect_serial()
            if not ok:
                QMessageBox.warning(self, "Pico Disconnected", f"Could not connect to Pico 2W:\n{msg}\nPlease ensure it is plugged in via USB.")
                self._refresh_pico_status()
                return

        ok, msg = bridge.trigger_type_credential(service, pwd, auto_enter=False)
        if ok:
            self.statusBar().showMessage(f"⚡ Injected {service} password into PC cursor via Pico!", 4000)
        else:
            QMessageBox.critical(self, "Typing Error", f"Pico failed to type password:\n{msg}")

    def _sync_to_pico_flash(self):
        bridge = self.vault_manager.pico_bridge
        if not bridge.is_connected_serial():
            ok, msg = bridge.connect_serial()
            if not ok:
                QMessageBox.warning(self, "Pico Disconnected", f"Could not connect to Pico 2W:\n{msg}")
                self._refresh_pico_status()
                return

        reply = QMessageBox.question(
            self, "Sync to Pico Memory",
            "This will flash your active vault credentials into the Pico 2W's internal Flash memory, "
            "allowing you to cycle and type them standalone with the Pico display & buttons without the PC app running.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            count, msg = bridge.sync_vault_to_pico(self.vault_manager.entries)
            QMessageBox.information(self, "Pico Flash Sync", msg)
            self._refresh_pico_status()

    def _refresh_pico_status(self):
        status = self.vault_manager.pico_bridge.get_status()
        if status.get("online"):
            dev = status.get("device", "Pico 2W")
            cnt = status.get("count", 0)
            mx = status.get("max", 32)
            self.pico_badge.setText(f"⚡ Pico: {dev} ({cnt}/{mx})")
            self.pico_badge.setStyleSheet("background-color: #313244; color: #a6e3a1; font-weight: bold; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        else:
            self.pico_badge.setText("⚡ Pico: Disconnected")
            self.pico_badge.setStyleSheet("background-color: #313244; color: #f38ba8; font-weight: bold; border-radius: 4px; padding: 4px 8px; font-size: 11px;")

    def closeEvent(self, event):
        self.vault_manager.pico_bridge.disconnect_serial()
        self.sync_server.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = OmniVaultApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
