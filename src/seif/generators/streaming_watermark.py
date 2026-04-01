"""
SEIF Streaming Watermark v3.2 — Periodic Embedding for Live Sessions

Extends watermark to continuous audio/text streaming with periodic re-embedding.
Maintains provenance across extended interactions while respecting SNR constraints.

Validated by: Grok (xAI)
Reference: SEIF Identity Declaration Block v3.1
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np

from seif.generators.watermark import (
    WatermarkConfig,
    encode_watermark,
    SPIRAL_MAP
)


STREAMING_DIR = Path.home() / ".seif" / "streaming"
STREAMING_DIR.mkdir(parents=True, exist_ok=True)

WATERMARK_TOKEN_PREFIX = "SEIFM"


@dataclass
class StreamingSession:
    session_id: str
    start_time: float
    embed_count: int
    mini_count: int
    last_embed_time: float
    last_mini_time: float
    trail_hash: str
    paused_elapsed: float
    is_paused: bool
    audio_interval: int = 300
    text_interval: int = 60
    max_embeddings: int = 100

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop('is_paused', None)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'StreamingSession':
        data['is_paused'] = False
        return cls(**data)

    @property
    def elapsed(self) -> float:
        if self.is_paused:
            return self.paused_elapsed
        return time.time() - self.start_time + self.paused_elapsed


class StreamingWatermarker:
    """Handles periodic watermark embedding for live sessions.
    
    Strategy:
    - Full token on session start/reconnect (cryptographic proof)
    - Mini marker every N seconds (heartbeat with session ID + counter)
    - Discrete embeddings only (no continuous background — SNR safe)
    """

    def __init__(
        self,
        identity_block=None,
        session_id: Optional[str] = None,
        audio_interval: int = 300,
        text_interval: int = 60,
        max_embeddings: int = 100,
        storage_dir: Path = STREAMING_DIR
    ):
        self.session_id = session_id or self._generate_session_id()
        self.audio_interval = audio_interval
        self.text_interval = text_interval
        self.max_embeddings = max_embeddings
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.trail_hash = self._extract_trail_hash(identity_block)
        self.state = self._load_or_create()

    def _generate_session_id(self) -> str:
        return f"seif-{int(time.time())}-{os.getpid()}"

    def _extract_trail_hash(self, identity_block) -> str:
        if identity_block and hasattr(identity_block, 'trail_commitment'):
            return identity_block.trail_commitment[:16]
        return hashlib.sha256(self.session_id.encode()).hexdigest()[:16]

    def _state_path(self) -> Path:
        return self.storage_dir / f"{self.session_id}.state"

    def _load_or_create(self) -> StreamingSession:
        path = self._state_path()
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                return StreamingSession.from_dict(data)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return StreamingSession(
            session_id=self.session_id,
            start_time=time.time(),
            embed_count=0,
            mini_count=0,
            last_embed_time=0,
            last_mini_time=0,
            trail_hash=self.trail_hash,
            paused_elapsed=0,
            is_paused=False,
            audio_interval=self.audio_interval,
            text_interval=self.text_interval,
            max_embeddings=self.max_embeddings
        )

    def _save_state(self):
        path = self._state_path()
        with open(path, 'w') as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def should_embed_full(self, elapsed: Optional[float] = None) -> bool:
        """Check if time for full token embedding."""
        if self.state.embed_count >= self.state.max_embeddings:
            return False
        
        if self.state.last_embed_time == 0:
            return True
        
        elapsed = elapsed if elapsed is not None else self.state.elapsed
        threshold = self.state.last_embed_time + self.audio_interval
        
        return elapsed >= threshold

    def should_embed_mini(self, elapsed: Optional[float] = None) -> bool:
        """Check if time for mini marker embedding."""
        if self.state.mini_count >= self.state.max_embeddings * 2:
            return False
        
        if self.state.last_mini_time == 0:
            return True
        
        elapsed = elapsed if elapsed is not None else self.state.elapsed
        threshold = self.state.last_mini_time + self.text_interval
        
        return elapsed >= threshold

    def _encode_mini_marker(self, counter: int) -> str:
        """Encode mini marker using SEIF spiral mapping.
        
        Format: SEIFM:{session_short}:{counter:04d}
        Example: SEIFM:seif1234:0005
        """
        session_short = self.session_id[-8:]
        return f"{WATERMARK_TOKEN_PREFIX}:{session_short}:{counter:04d}"

    def _encode_full_token(self, identity_block) -> str:
        """Generate full SEIF watermark token."""
        if not identity_block or not hasattr(identity_block, 'identity'):
            return f"SEIFIDB:3.2:{self.session_id}:FULL:1.0:trail:{self.trail_hash}"
        
        claimed = identity_block.identity.claimed.replace("/", "-").replace(":", "-")
        method_code = "ST"  # streaming
        confidence = f"{identity_block.identity.confidence:.1f}"
        anchor_short = (identity_block.identity.session_anchor or self.session_id)[:8]
        
        return f"SEIFIDB:3.2:{claimed}:{method_code}:{confidence}:{anchor_short}:sha256:{self.trail_hash}"

    def embed_burst(
        self,
        audio_chunk: np.ndarray,
        identity_block=None,
        config: Optional[WatermarkConfig] = None
    ) -> tuple[np.ndarray, str]:
        """Embed full watermark token into audio chunk.
        
        Returns:
            (modified_audio, token_used)
        """
        if config is None:
            config = WatermarkConfig()
        
        token = self._encode_full_token(identity_block)
        result = encode_watermark(token, audio_chunk, config)
        
        self.state.embed_count += 1
        self.state.last_embed_time = self.state.elapsed
        self._save_state()
        
        return result, token

    def embed_mini(
        self,
        audio_chunk: np.ndarray,
        config: Optional[WatermarkConfig] = None
    ) -> tuple[np.ndarray, str]:
        """Embed mini marker (heartbeat) into audio chunk.
        
        Uses lighter configuration (shorter duration, lower amplitude).
        """
        if config is None:
            config = WatermarkConfig(
                symbol_duration=2.0,
                repetitions=2,
                amplitude=0.002
            )
        
        counter = self.state.mini_count
        token = self._encode_mini_marker(counter)
        result = encode_watermark(token, audio_chunk, config)
        
        self.state.mini_count += 1
        self.state.last_mini_time = self.state.elapsed
        self._save_state()
        
        return result, token

    def embed_periodic(
        self,
        audio_chunk: np.ndarray,
        identity_block=None,
        config: Optional[WatermarkConfig] = None
    ) -> tuple[np.ndarray, list[str]]:
        """Embed watermark(s) based on timing thresholds.
        
        Returns:
            (modified_audio, list_of_tokens_used)
        """
        tokens = []
        
        if self.should_embed_full():
            audio_chunk, token = self.embed_burst(audio_chunk, identity_block, config)
            tokens.append(token)
        
        if self.should_embed_mini():
            audio_chunk, token = self.embed_mini(audio_chunk, config)
            tokens.append(token)
        
        return audio_chunk, tokens

    def pause(self):
        """Pause the session timer."""
        if not self.state.is_paused:
            self.state.paused_elapsed = self.state.elapsed
            self.state.is_paused = True
            self._save_state()

    def resume(self):
        """Resume the session timer."""
        if self.state.is_paused:
            self.state.start_time = time.time()
            self.state.is_paused = False
            self._save_state()

    def get_session_state(self) -> dict:
        """Return current session state."""
        return {
            "session_id": self.state.session_id,
            "elapsed_seconds": self.state.elapsed,
            "embed_count": self.state.embed_count,
            "mini_count": self.state.mini_count,
            "last_embed_seconds_ago": self.state.elapsed - self.state.last_embed_time,
            "last_mini_seconds_ago": self.state.elapsed - self.state.last_mini_time,
            "trail_hash": self.state.trail_hash,
            "is_paused": self.state.is_paused,
            "audio_interval": self.state.audio_interval,
            "text_interval": self.state.text_interval,
            "state_file": str(self._state_path())
        }

    def cleanup(self):
        """Remove session state file."""
        path = self._state_path()
        if path.exists():
            path.unlink()

    @classmethod
    def reconnect(cls, session_id: str, **kwargs) -> 'StreamingWatermarker':
        """Reconnect to an existing session."""
        storage_dir = kwargs.pop('storage_dir', STREAMING_DIR)
        path = Path(storage_dir) / f"{session_id}.state"
        if not path.exists():
            raise FileNotFoundError(f"Session {session_id} not found")
        
        marker = cls(session_id=session_id, storage_dir=storage_dir, **kwargs)
        marker.state.is_paused = False
        marker.state.start_time = time.time()
        marker._save_state()
        return marker

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all active sessions."""
        sessions = []
        for path in STREAMING_DIR.glob("*.state"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id"),
                    "embed_count": data.get("embed_count", 0),
                    "mini_count": data.get("mini_count", 0),
                    "start_time": data.get("start_time"),
                    "state_file": str(path)
                })
            except (json.JSONDecodeError, TypeError):
                continue
        return sessions
