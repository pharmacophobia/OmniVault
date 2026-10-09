# 🔐 OmniVault

> **Zero-Knowledge, AI-Augmented Cross-Platform Password Manager**  
> Direct AES-256-GCM + PBKDF2-HMAC-SHA256 encrypted database synchronization between Desktop (Linux/Windows/macOS) and Android, with local vision-based screenshot credential extraction (zero cloud dependencies) and native biometric authentication.

---

## 📥 Direct APK Download & Install

| Direct 1-Tap Download | Camera-Scannable QR Code |
| :---: | :---: |
| [![Download OmniVault APK](https://img.shields.io/badge/Download-OmniVault.apk-89b4fa?style=for-the-badge&logo=android&logoColor=white)](https://github.com/pharmacophobia/OmniVault/raw/main/OmniVault.apk)<br><br>[🔗 Direct Raw Download Link](https://github.com/pharmacophobia/OmniVault/raw/main/OmniVault.apk) | ![Scan QR Code to Install](https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=https://github.com/pharmacophobia/OmniVault/raw/main/OmniVault.apk) |

*Point your Android phone's camera at the QR code above to immediately download and install `OmniVault.apk`.*

---

## ✨ Features

- **📸 Local Vision Model Screenshot Extraction**:
  - Point your camera or take a screenshot of your login page/credentials.
  - Extracted entirely on your local machine using local neural OCR (`RapidOCR ONNX`) and local Ollama models (`llama3.2-vision` / `llava:7b` / `qwen2.5-coder`).
  - **Zero cloud telemetry**: Passwords and usernames are extracted on-device/on-LAN.
- **🛡️ Military-Grade Cryptography**:
  - Full end-to-end client-side encryption using **AES-256-GCM** with **PBKDF2-HMAC-SHA256** key derivation (100,000 iterations, random 128-bit salt, 96-bit nonce).
  - Cross-compatible cryptographic format between Python Desktop and Kotlin Android.
- **📱 Android App (Jetpack Compose + Material 3)**:
  - **Biometric Security**: Unlock with Fingerprint, Face ID, or system PIN via Android `androidx.biometric`.
  - **One-Tap Access**: Instant clipboard copy buttons for account names and passwords with auto-clear security.
  - **Integrated Password Generator**: Tunable entropy generator (uppercase, lowercase, numbers, symbols, ambiguous character filtering) with real-time strength indicators.
  - **Direct Wi-Fi P2P Sync**: Sync encrypted database directly with your desktop over local Wi-Fi.
- **🖥️ Desktop App (PyQt6)**:
  - Dark-mode, responsive credential management table.
  - Built-in lightweight P2P Sync HTTP server (`:8765`).
  - Direct Drag & Drop / File import for credential screenshots.
  - Built-in visual password generator.

---

## 🚀 Quick Start

### 1. Launch Desktop App

```bash
cd /home/k/OmniVault/desktop
python3 main.py
```

*Set a Master Password upon first launch. OmniVault will initialize your encrypted vault file at `~/.omnivault/vault.enc`.*

### 2. Install on Android Phone

1. Download [`OmniVault.apk`](https://github.com/pharmacophobia/OmniVault/raw/main/OmniVault.apk) using the QR code or link above.
2. Tap install.
3. Open **OmniVault**, enter your Master Password or tap **Unlock with Biometrics**.
4. In the top bar, tap **🔄 Sync** and enter your Desktop's IP address (default: `10.0.12.97`) to pull or push your encrypted database.
5. Tap **📸** to pick any screenshot of login credentials to automatically parse and store them!

---

## 🔒 Security Architecture

```
                  ┌───────────────────────────────┐
                  │       Master Password         │
                  └──────────────┬────────────────┘
                                 │ PBKDF2-HMAC-SHA256 (100k iter, random salt)
                                 ▼
                  ┌───────────────────────────────┐
                  │      AES-256 Encryption Key   │
                  └──────────────┬────────────────┘
                                 │ AES-256-GCM (12-byte IV + 128-bit Auth Tag)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Encrypted Vault Envelope                    │
│  - Salt (Base64)                                                │
│  - IV (Base64)                                                  │
│  - Ciphertext + Tag (Base64)                                    │
│  - Updated Timestamp                                            │
└─────────────────────────────────────────────────────────────────┘
          ▲                                               ▲
          │ P2P Sync (:8765)                              │ Local File
          ▼                                               ▼
┌──────────────────────────┐                    ┌──────────────────────────┐
│  Android OmniVault App   │                    │  Desktop OmniVault App   │
│  (Biometrics / Kotlin)   │                    │  (PyQt6 / Python)        │
└──────────────────────────┘                    └──────────────────────────┘
```
