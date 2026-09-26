"""
llama.cpp / vLLM local server integration using standard Python urllib.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional
from .base import LLMError, LLMUnavailableError, LocalLLM


class LlamaCppLocalLLM(LocalLLM):
    """Local llama.cpp HTTP server client."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8080",
        timeout_seconds: int = 30,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Call llama.cpp /completion endpoint."""
        url = f"{self.endpoint}/completion"
        full_prompt = f"<system>\n{system_prompt}\n</system>\n\n{prompt}" if system_prompt else prompt

        payload = {
            "prompt": full_prompt,
            "temperature": 0.1,
            "n_predict": 256,
            "stop": ["</s>", "\n\n\n"],
        }

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
                    raise LLMError(f"llama.cpp returned HTTP status {resp.status}")
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("content", "").strip()
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError) as e:
            raise LLMUnavailableError(
                f"llama.cpp local server unavailable at {self.endpoint}: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON returned by llama.cpp: {e}") from e
