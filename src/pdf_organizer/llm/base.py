"""
Protocols and error types for local LLM engines.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


class LLMError(Exception):
    """Base error for LLM execution issues."""
    pass


class LLMUnavailableError(LLMError):
    """Raised when the local LLM daemon is offline or unreachable."""
    pass


@runtime_checkable
class LocalLLM(Protocol):
    """Protocol for interchangeable local LLM backends."""

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate text from local model given prompt and optional system prompt."""
        ...
