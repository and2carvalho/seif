"""
Native AI Client — Direct SDK integration with Claude CLI fallback.

Supports streaming, multi-backend routing, and context injection from
the personal nucleus. When no ANTHROPIC_API_KEY is set, uses Claude CLI
(compatible with Max Plan via OAuth).
"""

from dataclasses import dataclass
from typing import Iterator, Optional
import os
import shutil
import subprocess


@dataclass
class ChatConfig:
    backend: str = "auto"         # claude, claude-cli, gemini, local, auto
    model: str = ""               # model override (empty = use default)
    stream: bool = True           # streaming responses
    quality_gate: bool = True     # measure every response
    max_tokens: int = 4096


# Default models per backend
_DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-6",
    "claude-cli": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-4-1-fast",
    "local": "llama3",
}


def _has_claude_cli() -> bool:
    return shutil.which("claude") is not None


class NativeClient:
    """Multi-backend AI client with streaming support."""

    def __init__(self, config: Optional[ChatConfig] = None,
                 profile: Optional[dict] = None):
        self.config = config or ChatConfig()
        self.profile = profile or {}
        self._backend = self._resolve_backend()
        self._model = self.config.model or _DEFAULT_MODELS.get(self._backend, "")
        self._client = None

    def _resolve_backend(self) -> str:
        """Resolve 'auto' to the best available backend."""
        if self.config.backend != "auto":
            return self.config.backend

        profile_default = self.profile.get("default_backend", "")
        if profile_default and profile_default != "auto":
            return profile_default

        # SDK requires API key with credits
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "claude"
        # No API key — prefer Claude CLI (Max Plan compatible)
        if _has_claude_cli():
            return "claude-cli"
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini"
        return "claude"

    def _get_anthropic_client(self):
        """Lazy-init Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def send(self, message: str, history: list[dict] = None,
             system: str = "") -> str:
        """Send message and return complete response."""
        if self._backend == "claude":
            return self._send_claude(message, history or [], system)
        elif self._backend == "claude-cli":
            return self._send_claude_cli(message, history or [], system)
        elif self._backend == "gemini":
            return self._send_gemini(message, history or [], system)
        elif self._backend == "local":
            return self._send_local(message, history or [], system)
        else:
            return f"Backend '{self._backend}' not supported."

    def stream(self, message: str, history: list[dict] = None,
               system: str = "") -> Iterator[str]:
        """Stream response tokens."""
        if self._backend == "claude":
            yield from self._stream_claude(message, history or [], system)
        elif self._backend == "claude-cli":
            yield from self._stream_claude_cli(message, history or [], system)
        else:
            yield self.send(message, history, system)

    # -- Claude SDK ------------------------------------------------

    def _send_claude(self, message: str, history: list[dict],
                     system: str) -> str:
        try:
            client = self._get_anthropic_client()
            messages = history + [{"role": "user", "content": message}]
            response = client.messages.create(
                model=self._model,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=messages,
            )
            return response.content[0].text
        except ImportError:
            return self._send_claude_cli(message, history, system)
        except Exception as e:
            return f"Error: {e}"

    def _stream_claude(self, message: str, history: list[dict],
                       system: str) -> Iterator[str]:
        try:
            client = self._get_anthropic_client()
            messages = history + [{"role": "user", "content": message}]
            with client.messages.stream(
                model=self._model,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except ImportError:
            yield from self._stream_claude_cli(message, history, system)
        except Exception as e:
            yield f"Error: {e}"

    # -- Claude CLI (Max Plan) -------------------------------------

    def _send_claude_cli(self, message: str, history: list[dict],
                         system: str) -> str:
        try:
            cmd = ["claude", "--print", "--output-format", "text",
                   "--no-session-persistence"]
            if system:
                cmd.extend(["--append-system-prompt", system])
            cmd.append(message)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.stdout.strip() if result.returncode == 0 else f"CLI error: {result.stderr.strip()}"
        except FileNotFoundError:
            return "Claude CLI not found. Install: https://docs.anthropic.com/claude-code"
        except subprocess.TimeoutExpired:
            return "Claude CLI timeout (300s)."
        except Exception as e:
            return f"CLI error: {e}"

    def _stream_claude_cli(self, message: str, history: list[dict],
                           system: str) -> Iterator[str]:
        """Stream from Claude CLI via subprocess pipe."""
        try:
            cmd = ["claude", "--print", "--output-format", "text",
                   "--no-session-persistence"]
            if system:
                cmd.extend(["--append-system-prompt", system])
            cmd.append(message)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            for line in proc.stdout:
                yield line
            proc.wait()
            if proc.returncode != 0:
                err = proc.stderr.read().strip()
                if err:
                    yield f"\nCLI error: {err}"
        except FileNotFoundError:
            yield "Claude CLI not found. Install: https://docs.anthropic.com/claude-code"
        except Exception as e:
            yield f"CLI error: {e}"

    # -- Gemini ----------------------------------------------------

    def _send_gemini(self, message: str, history: list[dict],
                     system: str) -> str:
        try:
            import google.generativeai as genai
            genai.configure()
            model = genai.GenerativeModel(self._model,
                                          system_instruction=system)
            chat = model.start_chat(history=[
                {"role": h["role"], "parts": [h["content"]]}
                for h in history
            ] if history else [])
            response = chat.send_message(message)
            return response.text
        except ImportError:
            return "Gemini SDK not installed. pip install google-generativeai"
        except Exception as e:
            return f"Gemini error: {e}"

    # -- Local (Ollama) --------------------------------------------

    def _send_local(self, message: str, history: list[dict],
                    system: str) -> str:
        try:
            result = subprocess.run(
                ["ollama", "run", self._model, message],
                capture_output=True, text=True, timeout=120,
            )
            return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr}"
        except FileNotFoundError:
            return "Ollama not installed. https://ollama.ai"
        except Exception as e:
            return f"Local error: {e}"
