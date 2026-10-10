from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from app_updater import AppUpdater

class UpdateWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, updater: AppUpdater):
        super().__init__()
        self.updater = updater

    def run(self):
        ok, msg = self.updater.perform_update(on_progress=lambda p: self.progress.emit(p))
        self.finished.emit(ok, msg)

class CheckWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, updater: AppUpdater):
        super().__init__()
        self.updater = updater

    def run(self):
        info = self.updater.check_for_updates()
        self.finished.emit(info)

class UpdateDialog(QDialog):
    def __init__(self, parent=None, repo_dir=None, app_name="Application", current_version="1.0.0"):
        super().__init__(parent)
        self.updater = AppUpdater(repo_dir=repo_dir, current_version=current_version)
        self.app_name = app_name
        self.setWindowTitle(f"🔄 Check for Updates — {app_name}")
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel { color: #cdd6f4; font-size: 13px; }
            QTextEdit { background-color: #313244; color: #ffffff; font-family: monospace; border: 1px solid #45475a; border-radius: 6px; padding: 8px; }
            QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px; padding: 8px 16px; }
            QPushButton:hover { background-color: #b4befe; }
        """)

        layout = QVBoxLayout(self)

        self.title_label = QLabel(f"🔄 {app_name} In-App Updater")
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #89b4fa;")
        layout.addWidget(self.title_label)

        self.version_label = QLabel(f"Current Version: v{current_version}  |  Checking remote...")
        layout.addWidget(self.version_label)

        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setPlaceholderText("Release notes will appear here...")
        layout.addWidget(self.notes_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Checking for updates on GitHub...")
        self.status_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("background-color: #45475a; color: #cdd6f4;")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        self.update_btn = QPushButton("🚀 Update Now")
        self.update_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._start_update)
        btn_layout.addWidget(self.update_btn)

        layout.addLayout(btn_layout)

        # Start check
        self.check_worker = CheckWorker(self.updater)
        self.check_worker.finished.connect(self._on_check_finished)
        self.check_worker.start()

    def _on_check_finished(self, info: dict):
        self.progress_bar.setVisible(False)
        if info.get("update_available"):
            latest = info.get("latest_version")
            commits = info.get("commits_behind", 0)
            self.version_label.setText(f"Current: v{self.updater.current_version}  ➜  Latest: v{latest} ({commits} commits ahead)")
            self.version_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.status_label.setText("An update is available! Click 'Update Now' to apply.")
            notes = info.get("release_notes", "") or "New updates available from remote."
            self.notes_box.setPlainText(notes)
            self.update_btn.setEnabled(True)
        else:
            self.version_label.setText(f"Current: v{self.updater.current_version} (Up to Date)")
            self.status_label.setText(f"{self.app_name} is already at the latest version.")
            self.notes_box.setPlainText("No new updates found. You are running the newest release!")

    def _start_update(self):
        self.update_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Downloading and applying updates...")

        self.update_worker = UpdateWorker(self.updater)
        self.update_worker.progress.connect(lambda p: self.status_label.setText(p))
        self.update_worker.finished.connect(self._on_update_finished)
        self.update_worker.start()

    def _on_update_finished(self, success: bool, msg: str):
        self.progress_bar.setVisible(False)
        if success:
            reply = QMessageBox.question(
                self, "Update Complete",
                f"{msg}\n\nWould you like to restart {self.app_name} now to apply changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.updater.restart_application()
            else:
                self.accept()
        else:
            QMessageBox.critical(self, "Update Failed", msg)
            self.update_btn.setEnabled(True)
            self.status_label.setText("Update failed. Check your network connection.")
