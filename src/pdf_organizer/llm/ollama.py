"""
Ollama local inference integration using standard Python urllib.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional
from .base import LLMError, LLMUnavailableError, LocalLLM


class OllamaLocalLLM(LocalLLM):
    """Local Ollama client communicating over loopback HTTP."""

    def __init__(
        self,
        model: str = "llama3.2",
        endpoint: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 30,
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Call Ollama /api/generate."""
        url = f"{self.endpoint}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic classification
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status != 200:
                    raise LLMError(f"Ollama returned HTTP status {resp.status}")
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("response", "").strip()
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError) as e:
            raise LLMUnavailableError(
                f"Ollama local instance unavailable at {self.endpoint}: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON returned by Ollama: {e}") from e
