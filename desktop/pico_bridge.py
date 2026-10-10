import time
from typing import List, Dict, Optional, Tuple, Union, Any
import serial
import serial.tools.list_ports
import requests

class PicoTyperBridge:
    """
    Direct bridge between OmniVault and the Raspberry Pi Pico 2W Password Typer.
    Supports:
      - USB Serial (CDC) via /dev/ttyACM*
      - Wi-Fi REST API (http://192.168.4.1 or custom IP)
      - Direct typing / injection of any vault credential
      - Syncing vault credentials to Pico onboard memory (Flash)
      - Real-time device status and memory usage
    """
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, wifi_url: str = "http://192.168.4.1"):
        self.port = port
        self.baudrate = baudrate
        self.wifi_url = wifi_url.rstrip("/")
        self.ser: Optional[serial.Serial] = None

    @classmethod
    def find_pico_ports(cls) -> List[Tuple[str, str]]:
        """Scans system for connected Raspberry Pi Pico devices."""
        pico_ports = []
        other_ports = []
        for p in serial.tools.list_ports.comports():
            # Check Raspberry Pi VID (0x2e8a) or descriptor keywords
            is_pico = (p.vid == 0x2e8a) or ("pico" in p.description.lower())
            item = (p.device, p.description)
            if is_pico:
                pico_ports.append(item)
            else:
                other_ports.append(item)
        return pico_ports + other_ports

    def connect_serial(self, port: Optional[str] = None) -> Tuple[bool, str]:
        if port:
            self.port = port
        if not self.port:
            candidate_ports = self.find_pico_ports()
            if candidate_ports:
                self.port = candidate_ports[0][0]
            else:
                return False, "No serial port found"

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1.0)
            time.sleep(0.08)
            self.ser.reset_input_buffer()
            self.ser.write(b"PING\r\n")
            line = self.ser.readline().decode("utf-8", errors="replace").strip()
            if "PONG" in line:
                return True, f"Connected to Pico on {self.port}"
            return True, f"Connected to {self.port} (unverified PING response: {line})"
        except Exception as e:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = None
            return False, f"Failed to connect to {self.port}: {str(e)}"

    def disconnect_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def is_connected_serial(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def send_cmd(self, cmd: str) -> str:
        # Check connection; if closed or missing, attempt reconnect
        if not self.is_connected_serial():
            ok, _ = self.connect_serial()
            if not ok:
                raise ConnectionError("Pico serial port not connected")

        try:
            self.ser.reset_input_buffer()
            self.ser.write((cmd.strip() + "\r\n").encode("utf-8"))
            self.ser.flush()
            line = self.ser.readline().decode("utf-8", errors="replace").strip()
            return line
        except (serial.SerialException, OSError) as e:
            # Stale handle from reboot/flashing or unbind; re-open and retry once
            self.disconnect_serial()
            ok, _ = self.connect_serial()
            if ok and self.ser and self.ser.is_open:
                try:
                    self.ser.reset_input_buffer()
                    self.ser.write((cmd.strip() + "\r\n").encode("utf-8"))
                    self.ser.flush()
                    return self.ser.readline().decode("utf-8", errors="replace").strip()
                except Exception as inner_e:
                    raise inner_e
            raise e

    def get_status(self) -> Dict[str, Any]:
        """Returns hardware status, stored script count, capacity, and IP."""
        if not self.is_connected_serial():
            # Try WiFi fallback
            try:
                r = requests.get(f"{self.wifi_url}/api/scripts", timeout=1.5)
                if r.status_code == 200:
                    scripts = r.json()
                    return {
                        "online": True,
                        "mode": "WiFi",
                        "count": len(scripts),
                        "max": 32,
                        "ip": self.wifi_url
                    }
            except Exception:
                pass
            return {"online": False, "mode": "Disconnected", "count": 0, "max": 32, "ip": ""}

        try:
            resp = self.send_cmd("STATUS")
            parts = resp.split("|")
            if len(parts) >= 6 and parts[0] == "STATUS":
                return {
                    "online": True,
                    "mode": "USB Serial",
                    "device": parts[1],
                    "version": parts[2],
                    "count": int(parts[3]),
                    "max": int(parts[4]),
                    "ip": parts[5]
                }
            return {"online": True, "mode": "USB Serial", "count": 0, "max": 32, "ip": ""}
        except Exception as e:
            return {"online": False, "mode": "Error", "error": str(e)}

    def get_pico_scripts(self) -> List[Dict[str, Any]]:
        """Retrieves all macros currently stored in Pico memory."""
        if not self.is_connected_serial():
            ok, _ = self.connect_serial()
            if not ok:
                # Fallback to WiFi
                try:
                    r = requests.get(f"{self.wifi_url}/api/scripts", timeout=2.0)
                    if r.status_code == 200:
                        return r.json()
                except Exception:
                    pass
                return []

        try:
            self.ser.reset_input_buffer()
            self.ser.write(b"LIST\r\n")
            self.ser.flush()

            scripts = []
            header = self.ser.readline().decode("utf-8", errors="replace").strip()
            if not header.startswith("SCRIPTS_START"):
                return scripts

            while True:
                line = self.ser.readline().decode("utf-8", errors="replace").strip()
                if not line or line == "SCRIPTS_END":
                    break
                parts = line.split("|", 4)
                if len(parts) >= 5 and parts[0] == "SCRIPT":
                    scripts.append({
                        "id": int(parts[1]),
                        "auto_enter": (parts[2] == "1"),
                        "name": parts[3],
                        "payload": parts[4]
                    })
            return scripts
        except Exception:
            self.disconnect_serial()
            return []

    def trigger_type_slot(self, slot_id: int) -> Tuple[bool, str]:
        """Tells the Pico to immediately type keystrokes from slot ID."""
        if self.is_connected_serial():
            try:
                resp = self.send_cmd(f"RUN|{slot_id}")
                return ("OK:RAN" in resp), resp
            except Exception as e:
                return False, str(e)
        else:
            try:
                r = requests.get(f"{self.wifi_url}/type", params={"id": slot_id}, timeout=2.0)
                return (r.status_code in [200, 302]), "Typed via WiFi"
            except Exception as e:
                return False, str(e)

    def trigger_type_credential(self, label: str, secret_text: str, auto_enter: bool = False) -> Tuple[bool, str]:
        """
        Dynamically stages and types the credential immediately via Pico HID keyboard.
        Uses slot 31 (reserved for dynamic live typing) or writes an entry and triggers RUN.
        """
        clean_name = f"Live:{label}"[:31].replace("|", "-")
        clean_payload = secret_text.replace("\r\n", "\\n").replace("\n", "\\n").replace("|", "\\|")
        enter_flag = "1" if auto_enter else "0"

        if self.is_connected_serial():
            try:
                # Check current scripts to update existing or add
                scripts = self.get_pico_scripts()
                target_slot = None
                for s in scripts:
                    if s["name"].startswith("Live:"):
                        target_slot = s["id"]
                        break

                if target_slot is not None:
                    # Update slot
                    resp = self.send_cmd(f"UPDATE|{target_slot}|{clean_name}|{enter_flag}|{clean_payload}")
                else:
                    # Add slot
                    resp = self.send_cmd(f"ADD|{clean_name}|{enter_flag}|{clean_payload}")
                    if "OK:ADDED|" in resp:
                        target_slot = int(resp.split("|")[1])

                if target_slot is not None:
                    run_resp = self.send_cmd(f"RUN|{target_slot}")
                    return True, f"Injected into computer via Pico (Slot {target_slot})!"
                return False, f"Failed to stage credential on Pico: {resp}"
            except Exception as e:
                return False, str(e)
        else:
            # WiFi fallback
            try:
                r = requests.get(f"{self.wifi_url}/add", params={
                    "name": clean_name,
                    "payload": secret_text,
                    "enter": enter_flag
                }, timeout=2.5)
                # Then trigger type on last item
                scripts = self.get_pico_scripts()
                if scripts:
                    last_id = scripts[-1]["id"]
                    requests.get(f"{self.wifi_url}/type", params={"id": last_id}, timeout=2.0)
                    return True, f"Injected via Pico WiFi (Slot {last_id})!"
                return False, "Failed to inject via WiFi"
            except Exception as e:
                return False, str(e)

    def sync_vault_to_pico(self, vault_entries: List[Dict[str, Any]], max_slots: int = 16) -> Tuple[int, str]:
        """
        Uploads selected vault passwords to Pico onboard memory (Flash) so they
        are available standalone even when disconnected from the desktop!
        """
        if not self.is_connected_serial():
            return 0, "Pico serial connection not available"

        try:
            # Clear existing scripts
            self.send_cmd("CLEAR")
            count = 0
            for i, entry in enumerate(vault_entries[:max_slots]):
                service = entry.get("service", "Account").replace("|", "-")
                account = entry.get("account", "").replace("|", "-")
                name = f"{service} ({account})"[:31] if account else service[:31]
                payload = entry.get("password", "")
                if not payload:
                    continue
                clean_payload = payload.replace("\r\n", "\\n").replace("\n", "\\n").replace("|", "\\|")
                resp = self.send_cmd(f"ADD|{name}|0|{clean_payload}")
                if "OK:ADDED" in resp:
                    count += 1
            return count, f"Successfully flashed {count} credentials to Pico standalone memory!"
        except Exception as e:
            return 0, f"Sync error: {str(e)}"
