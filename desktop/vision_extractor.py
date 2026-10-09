import base64
import json
import os
import re
import requests
from typing import Dict, Any, Optional, Tuple

class VisionExtractor:
    """
    Hybrid Vision & OCR Credential Extractor.
    1. First uses high-speed local Neural OCR (RapidOCR ONNX) for zero-hallucination text localization.
    2. Then uses local Ollama Vision/LLM (e.g. llama3.1, deepseek-r1, or llama3.2-vision) to parse
       and structure complex unstructured screenshots into structured credentials (service, account, password).
    """
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llava:7b"):
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model
        self.ocr_engine = None
        self._init_ocr()

    def _init_ocr(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr_engine = RapidOCR()
        except Exception:
            self.ocr_engine = None

    def check_connection(self) -> Tuple[bool, str]:
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                ocr_status = "RapidOCR Active" if self.ocr_engine else "OCR Unavailable"
                return True, f"Ollama Connected ({len(models)} models available) | {ocr_status}"
            return False, f"Ollama returned HTTP {resp.status_code}"
        except Exception as e:
            return False, f"Cannot connect to Ollama at {self.ollama_url}: {e}"

    def extract_from_image(self, image_path: str) -> Dict[str, str]:
        """
        Extracts credentials from screenshot image file.
        Returns dict with keys: 'service', 'account', 'password', 'raw_output'.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        extracted_lines = []
        if self.ocr_engine:
            try:
                ocr_results, _ = self.ocr_engine(image_path)
                if ocr_results:
                    for item in ocr_results:
                        if len(item) >= 2 and item[1]:
                            extracted_lines.append(str(item[1]).strip())
            except Exception as e:
                pass

        ocr_text = "\n".join(extracted_lines)

        # First try heuristic extraction directly from OCR text
        heuristic = self._parse_heuristics(ocr_text)
        if heuristic["account"] and heuristic["password"]:
            heuristic["raw_output"] = ocr_text
            return heuristic

        # If incomplete or complex, query local LLM to structure the extracted visual text
        llm_parsed = self._query_llm_parser(ocr_text, image_path)
        if llm_parsed.get("password") or llm_parsed.get("account"):
            return llm_parsed

        # Fallback to whatever OCR detected
        heuristic["raw_output"] = ocr_text
        return heuristic

    def _query_llm_parser(self, ocr_text: str, image_path: str) -> Dict[str, str]:
        # Use fast local reasoning model to parse the visual text
        prompt = (
            "You are a credential parser for a password manager. Given this text extracted from a screenshot:\n"
            f"```\n{ocr_text}\n```\n\n"
            "Extract the login credentials and output ONLY a valid JSON object with these exact keys:\n"
            "{\n"
            '  "service": "<App, company, or website name>",\n'
            '  "account": "<Email, username, or login ID>",\n'
            '  "password": "<Plain text password or secret>"\n'
            "}\n"
            "Do not include any explanation or extra text. Output strict JSON only."
        )

        for candidate_model in ["qwen2.5-coder:3b", "llama3.1:8b", "deepseek-r1:7b"]:
            try:
                resp = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": candidate_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    },
                    timeout=20
                )
                if resp.status_code == 200:
                    text_resp = resp.json().get("response", "").strip()
                    parsed = self._parse_json(text_resp)
                    if parsed["password"] or parsed["account"]:
                        parsed["raw_output"] = text_resp
                        return parsed
            except Exception:
                continue

        return {"service": "", "account": "", "password": "", "raw_output": ocr_text}

    def _parse_heuristics(self, text: str) -> Dict[str, str]:
        service = ""
        account = ""
        password = ""

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            # Service
            m_s = re.search(r'(?:service|website|site|app)[:=\s]+([^\r\n]+)', line, re.IGNORECASE)
            if m_s: service = m_s.group(1).strip()

            # Account / Email
            m_a = re.search(r'(?:email|username|user|account|login)[:=\s]+([^\r\n]+)', line, re.IGNORECASE)
            if m_a:
                account = m_a.group(1).strip()
            elif "@" in line and not account:
                # Raw email found
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
                if email_match:
                    account = email_match.group(0)

            # Password
            m_p = re.search(r'(?:password|pass|secret)[:=\s]+([^\r\n]+)', line, re.IGNORECASE)
            if m_p: password = m_p.group(1).strip()

        # If service still empty and we have a title line
        if not service and lines:
            first = lines[0]
            if not any(k in first.lower() for k in ["credential", "login", "account", "password", "email"]):
                service = first

        return {"service": service, "account": account, "password": password}

    def _parse_json(self, text: str) -> Dict[str, str]:
        clean_text = text
        if "```" in clean_text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
            if match:
                clean_text = match.group(1).strip()

        try:
            obj = json.loads(clean_text)
            if isinstance(obj, dict):
                return {
                    "service": str(obj.get("service", "") or "").strip(),
                    "account": str(obj.get("account", "") or "").strip(),
                    "password": str(obj.get("password", "") or "").strip()
                }
        except Exception:
            pass

        return self._parse_heuristics(text)
