import http.server
import socketserver
import threading
import json
import os
import base64
from typing import Callable, Optional

class SyncServerHandler(http.server.BaseHTTPRequestHandler):
    vault_manager = None # Injected by SyncServer

    def _send_json(self, status: int, data: dict):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/status":
            self._send_json(200, {
                "status": "online",
                "app": "OmniVault Sync Server",
                "version": "1.0.0",
                "vault_loaded": self.vault_manager.is_vault_loaded() if self.vault_manager else False,
                "has_vault_file": self.vault_manager.has_vault_file() if self.vault_manager else False
            })
        elif self.path == "/api/vault/encrypted":
            # Downloads the encrypted vault envelope
            if not self.vault_manager or not self.vault_manager.has_vault_file():
                self._send_json(404, {"error": "Vault file not found on desktop"})
                return
            envelope = self.vault_manager.get_encrypted_envelope()
            self._send_json(200, envelope)
        elif self.path == "/api/pico/status":
            if hasattr(self.vault_manager, "pico_bridge") and self.vault_manager.pico_bridge:
                self._send_json(200, self.vault_manager.pico_bridge.get_status())
            else:
                self._send_json(200, {"online": False, "mode": "Unavailable"})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        if self.path == "/api/vault/sync":
            # Phone pushes updated encrypted vault envelope
            try:
                payload = json.loads(post_data.decode("utf-8"))
                if not self.vault_manager:
                    self._send_json(500, {"error": "Vault manager not initialized"})
                    return
                ok, msg = self.vault_manager.save_encrypted_envelope_from_remote(payload)
                if ok:
                    self._send_json(200, {"status": "success", "message": msg})
                else:
                    self._send_json(400, {"error": msg})
            except Exception as e:
                self._send_json(400, {"error": f"Invalid sync payload: {str(e)}"})

        elif self.path == "/api/vision/extract":
            # Phone sends screenshot to desktop's local Ollama vision model
            try:
                payload = json.loads(post_data.decode("utf-8"))
                image_b64 = payload.get("image_base64", "")
                if not image_b64:
                    self._send_json(400, {"error": "image_base64 is required"})
                    return

                # Save temporary image to inspect
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(base64.b64decode(image_b64))
                    tmp_path = tmp.name

                try:
                    result = self.vault_manager.vision_extractor.extract_from_image(tmp_path)
                    self._send_json(200, {"status": "success", "data": result})
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            except Exception as e:
                self._send_json(500, {"error": f"Vision extraction failed: {str(e)}"})

        elif self.path == "/api/pico/type":
            # Remote trigger from Android to inject credentials into computer via Pico HID
            try:
                payload = json.loads(post_data.decode("utf-8"))
                label = payload.get("label", "Mobile App")
                text_to_type = payload.get("text", "")
                auto_enter = payload.get("auto_enter", False)
                if not text_to_type:
                    self._send_json(400, {"error": "text is required"})
                    return

                if hasattr(self.vault_manager, "pico_bridge") and self.vault_manager.pico_bridge:
                    ok, msg = self.vault_manager.pico_bridge.trigger_type_credential(label, text_to_type, auto_enter)
                    self._send_json(200 if ok else 500, {"success": ok, "message": msg})
                else:
                    self._send_json(503, {"error": "Pico bridge not connected"})
            except Exception as e:
                self._send_json(500, {"error": f"Failed to type via Pico: {str(e)}"})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        # Suppress noisy standard output logging
        pass

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class SyncServer:
    def __init__(self, vault_manager, port: int = 8765):
        self.vault_manager = vault_manager
        self.port = port
        self.server: Optional[ThreadedHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    def start(self):
        if self.running:
            return
        SyncServerHandler.vault_manager = self.vault_manager
        self.server = ThreadedHTTPServer(("0.0.0.0", self.port), SyncServerHandler)
        self.running = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
