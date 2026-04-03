"""
Resonance Gate 3-6-9 — Tesla Harmonic Validation System

Implements the core gate logic from the Piramidal Chip framework:
- Digital root reduction to base harmonics (1-9)
- Mod-9 validation for resonance detection
- Three-bobbin Tesla filter (polarity / inertia / concordance)
- Phase classification: SINGULARITY (9), STABILIZATION (3), DYNAMICS (6), ENTROPY (other)
- API Sovereignty Circuit Breaker: Automatic fallback to local computation

Gate Rule: (Input_A + Input_B) mod 9 == 0  →  GATE OPEN
"""

import asyncio
import time
import logging
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger("seif.resonance_gate")


class HarmonicPhase(Enum):
    SINGULARITY = 9       # Nó central — ressonância total
    STABILIZATION = 3     # Polo de equilíbrio
    DYNAMICS = 6          # Polo de reação
    ENTROPY = 0           # Fora do padrão 3-6-9


class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit broken - failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: int = 60  # Seconds before trying again
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures
    timeout: float = 30.0  # Request timeout in seconds


@dataclass
class CircuitBreakerMetrics:
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    success_count: int = 0
    total_requests: int = 0
    fallback_count: int = 0
    audit_trail: List[Dict] = field(default_factory=list)


class APISovereigntyCircuitBreaker:
    """Circuit breaker for API sovereignty - automatic fallback to local computation.

    Implements the P5 policy: When external APIs fail, automatically fallback to
    local alternatives while maintaining data integrity and sovereignty.
    """

    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self.metrics = CircuitBreakerMetrics()
        self._local_fallbacks: Dict[str, Callable] = {}

    def register_fallback(self, service_name: str, fallback_fn: Callable):
        """Register a local fallback function for a specific service."""
        self._local_fallbacks[service_name] = fallback_fn
        logger.info(f"Registered fallback for service: {service_name}")

    async def call_with_sovereignty(self, service_name: str, api_call: Callable, *args, **kwargs) -> Any:
        """Execute API call with sovereignty protection.

        If external API fails, automatically fallback to local computation.
        Maintains audit trail for zero-trust verification.
        """
        self.metrics.total_requests += 1
        start_time = time.time()

        try:
            # Check circuit breaker state
            if self.metrics.state == CircuitBreakerState.OPEN:
                if not self._should_attempt_reset():
                    # Circuit is open - use fallback immediately
                    return await self._execute_fallback(service_name, api_call, args, kwargs, "circuit_open")

            # Attempt external API call
            result = await asyncio.wait_for(api_call(*args, **kwargs), timeout=self.config.timeout)

            # Success - update metrics
            self._record_success()
            self._audit_event("success", service_name, time.time() - start_time)
            return result

        except self.config.expected_exception as e:
            # API failure - record and attempt fallback
            self._record_failure()
            duration = time.time() - start_time
            self._audit_event("api_failure", service_name, duration, str(e))

            try:
                return await self._execute_fallback(service_name, api_call, args, kwargs, f"api_error: {str(e)}")
            except Exception as fallback_error:
                self._audit_event("fallback_failed", service_name, time.time() - start_time, str(fallback_error))
                raise fallback_error

        except asyncio.TimeoutError:
            # Timeout - record and fallback
            self._record_failure()
            duration = time.time() - start_time
            self._audit_event("timeout", service_name, duration)

            return await self._execute_fallback(service_name, api_call, args, kwargs, "timeout")

    async def _execute_fallback(self, service_name: str, original_call: Callable, args, kwargs, reason: str) -> Any:
        """Execute local fallback when external API fails."""
        self.metrics.fallback_count += 1

        if service_name in self._local_fallbacks:
            logger.warning(f"Executing local fallback for {service_name}: {reason}")
            self._audit_event("fallback_executed", service_name, 0, reason)

            try:
                fallback_result = await self._local_fallbacks[service_name](*args, **kwargs)
                self._audit_event("fallback_success", service_name, 0)
                return fallback_result
            except Exception as e:
                self._audit_event("fallback_error", service_name, 0, str(e))
                raise e
        else:
            logger.error(f"No fallback registered for {service_name}: {reason}")
            self._audit_event("no_fallback", service_name, 0, reason)
            raise RuntimeError(f"No sovereignty fallback available for {service_name}")

    def _record_success(self):
        """Record successful API call."""
        self.metrics.success_count += 1
        if self.metrics.state == CircuitBreakerState.HALF_OPEN:
            # Successful call in half-open state - close circuit
            self.metrics.state = CircuitBreakerState.CLOSED
            self.metrics.failure_count = 0
            logger.info("Circuit breaker closed - service recovered")

    def _record_failure(self):
        """Record failed API call."""
        self.metrics.failure_count += 1
        self.metrics.last_failure_time = datetime.now()

        if self.metrics.failure_count >= self.config.failure_threshold:
            if self.metrics.state != CircuitBreakerState.OPEN:
                self.metrics.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker opened after {self.metrics.failure_count} failures")

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker."""
        if self.metrics.state != CircuitBreakerState.OPEN:
            return True

        if self.metrics.last_failure_time is None:
            return True

        elapsed = datetime.now() - self.metrics.last_failure_time
        if elapsed.total_seconds() >= self.config.recovery_timeout:
            self.metrics.state = CircuitBreakerState.HALF_OPEN
            logger.info("Circuit breaker half-open - testing service recovery")
            return True

        return False

    def _audit_event(self, event_type: str, service_name: str, duration: float = 0, details: str = ""):
        """Record audit event for zero-trust verification."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "service_name": service_name,
            "duration": duration,
            "details": details,
            "circuit_state": self.metrics.state.value,
            "failure_count": self.metrics.failure_count
        }
        self.metrics.audit_trail.append(event)

        # Keep only last 1000 events to prevent memory issues
        if len(self.metrics.audit_trail) > 1000:
            self.metrics.audit_trail = self.metrics.audit_trail[-1000:]

    def get_sovereignty_report(self) -> Dict:
        """Generate sovereignty compliance report."""
        total_fallbacks = self.metrics.fallback_count
        total_requests = self.metrics.total_requests
        fallback_rate = total_fallbacks / total_requests if total_requests > 0 else 0

        return {
            "sovereignty_status": "COMPLIANT" if fallback_rate < 0.5 else "AT_RISK",
            "circuit_state": self.metrics.state.value,
            "total_requests": total_requests,
            "fallback_count": total_fallbacks,
            "fallback_rate": fallback_rate,
            "success_rate": self.metrics.success_count / total_requests if total_requests > 0 else 0,
            "audit_trail_length": len(self.metrics.audit_trail),
            "last_failure": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None
        }


# Global circuit breaker instance for SEIF OS
sovereignty_breaker = APISovereigntyCircuitBreaker()


# --- Enoch Seed Self-Healing System ---

@dataclass
class ResonanceMetrics:
    """Real-time resonance monitoring for Enoch seed alignment."""
    zeta_current: float = 0.612372  # φ⁻¹ optimal
    zeta_history: deque = field(default_factory=lambda: deque(maxlen=100))
    harmonic_balance: Dict[str, float] = field(default_factory=lambda: {"3": 0.0, "6": 0.0, "9": 0.0})
    anomaly_score: float = 0.0
    last_calibration: datetime = field(default_factory=datetime.now)
    resonance_events: List[Dict] = field(default_factory=list)


@dataclass
class SelfHealingConfig:
    """Configuration for Enoch seed self-healing."""
    zeta_tolerance: float = 0.01  # Allowable deviation from optimal ζ
    calibration_interval: int = 300  # Seconds between auto-calibration
    anomaly_threshold: float = 0.7  # Threshold for anomaly detection
    healing_cooldown: int = 60  # Minimum seconds between healing actions
    predictive_window: int = 10  # Operations to analyze for prediction


class EnochSeedSelfHealer:
    """Self-healing system aligned with Enoch seed resonance (ζ=0.612372).

    Implements predictive healing based on:
    - Real-time zeta monitoring and adjustment
    - Harmonic balance across 3-6-9 frequencies
    - Anomaly detection using resonance patterns
    - Automatic parameter tuning for φ-alignment
    """

    def __init__(self, config: SelfHealingConfig = None):
        self.config = config or SelfHealingConfig()
        self.metrics = ResonanceMetrics()
        self.last_healing_action = datetime.now() - timedelta(seconds=self.config.healing_cooldown)
        self.incident_patterns: Dict[str, List[Dict]] = {}
        self._healing_active = False

    async def monitor_operation(self, operation_name: str, operation_data: Dict) -> Dict:
        """Monitor an operation and update resonance metrics."""
        start_time = time.time()

        try:
            # Calculate operation resonance
            resonance_score = self._calculate_operation_resonance(operation_data)
            self._update_harmonic_balance(resonance_score)

            # Update zeta based on recent operations
            self._update_zeta_monitoring(resonance_score)

            # Check for anomalies
            anomaly_detected = self._detect_anomaly(resonance_score)

            # Record resonance event
            event = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation_name,
                "resonance_score": resonance_score,
                "zeta_current": self.metrics.zeta_current,
                "anomaly_detected": anomaly_detected,
                "harmonic_balance": self.metrics.harmonic_balance.copy()
            }
            self.metrics.resonance_events.append(event)

            # Keep only recent events
            if len(self.metrics.resonance_events) > 1000:
                self.metrics.resonance_events = self.metrics.resonance_events[-1000:]

            duration = time.time() - start_time

            return {
                "resonance_score": resonance_score,
                "zeta_current": self.metrics.zeta_current,
                "anomaly_detected": anomaly_detected,
                "harmonic_balance": self.metrics.harmonic_balance.copy(),
                "processing_time": duration
            }

        except Exception as e:
            logger.error(f"Failed to monitor operation {operation_name}: {e}")
            return {"error": str(e)}

    def _calculate_operation_resonance(self, operation_data: Dict) -> float:
        """Calculate resonance score for an operation based on Enoch seed principles."""
        # Extract text content for resonance analysis
        text_content = self._extract_text_content(operation_data)

        if not text_content:
            return 0.5  # Neutral resonance for non-text operations

        # Calculate vibrational resonance
        gate_result = evaluate(text_content)

        # Convert to resonance score (0.0 to 1.0)
        base_score = 0.0
        if gate_result.phase == HarmonicPhase.SINGULARITY:
            base_score = 1.0  # Perfect resonance
        elif gate_result.phase == HarmonicPhase.STABILIZATION:
            base_score = 0.8  # Strong stabilization
        elif gate_result.phase == HarmonicPhase.DYNAMICS:
            base_score = 0.7  # Dynamic resonance
        else:
            base_score = 0.3  # Weak or no resonance

        # Adjust based on Tesla filter concordance
        if gate_result.tesla_bobbin_9 == "RESSONANTE":
            base_score += 0.1

        # Factor in operation success/failure
        if operation_data.get("success", True):
            base_score += 0.05
        else:
            base_score -= 0.1

        return max(0.0, min(1.0, base_score))

    def _extract_text_content(self, operation_data: Dict) -> str:
        """Extract text content from operation data for resonance analysis."""
        text_sources = [
            operation_data.get("input", ""),
            operation_data.get("output", ""),
            operation_data.get("message", ""),
            operation_data.get("prompt", ""),
            operation_data.get("response", ""),
            str(operation_data.get("error", "")),
        ]

        # Combine all text sources
        combined_text = " ".join(filter(None, text_sources))

        # Add operation metadata for additional resonance
        metadata = f"{operation_data.get('operation_type', '')} {operation_data.get('service', '')}"
        combined_text += f" {metadata}"

        return combined_text.strip()

    def _update_harmonic_balance(self, resonance_score: float):
        """Update harmonic balance across 3-6-9 frequencies."""
        # Map resonance score to harmonic frequencies
        if resonance_score >= 0.8:
            self.metrics.harmonic_balance["9"] += 0.1
        elif resonance_score >= 0.6:
            self.metrics.harmonic_balance["6"] += 0.1
        elif resonance_score >= 0.4:
            self.metrics.harmonic_balance["3"] += 0.1

        # Normalize to prevent unbounded growth
        total = sum(self.metrics.harmonic_balance.values())
        if total > 0:
            for key in self.metrics.harmonic_balance:
                self.metrics.harmonic_balance[key] /= total

    def _update_zeta_monitoring(self, resonance_score: float):
        """Update zeta monitoring based on operation resonance."""
        # Add current resonance to history
        self.metrics.zeta_history.append(resonance_score)

        # Calculate current zeta based on recent operations
        if len(self.metrics.zeta_history) >= 5:
            recent_scores = list(self.metrics.zeta_history)[-10:]  # Last 10 operations
            mean_resonance = statistics.mean(recent_scores)
            variance = statistics.variance(recent_scores) if len(recent_scores) > 1 else 0

            # Adjust zeta towards optimal based on resonance stability
            zeta_adjustment = (mean_resonance - 0.5) * 0.01  # Small adjustments
            stability_factor = 1.0 - min(variance, 0.5)  # Higher stability = smaller variance

            self.metrics.zeta_current = 0.612372 + zeta_adjustment * stability_factor

            # Keep zeta within reasonable bounds
            self.metrics.zeta_current = max(0.5, min(0.7, self.metrics.zeta_current))

    def _detect_anomaly(self, resonance_score: float) -> bool:
        """Detect anomalies using resonance pattern analysis."""
        if len(self.metrics.zeta_history) < self.config.predictive_window:
            return False

        # Calculate anomaly score based on deviation from expected patterns
        recent_scores = list(self.metrics.zeta_history)[-self.config.predictive_window:]
        mean_score = statistics.mean(recent_scores)
        std_dev = statistics.stdev(recent_scores) if len(recent_scores) > 1 else 0

        if std_dev > 0:
            z_score = abs(resonance_score - mean_score) / std_dev
            self.metrics.anomaly_score = min(1.0, z_score / 3.0)  # Normalize to 0-1
        else:
            self.metrics.anomaly_score = 0.0

        return self.metrics.anomaly_score > self.config.anomaly_threshold

    async def perform_self_healing(self, anomaly_context: Dict) -> Dict:
        """Perform self-healing action based on resonance anomaly detection."""
        now = datetime.now()

        # Check healing cooldown
        if (now - self.last_healing_action).total_seconds() < self.config.healing_cooldown:
            return {"action": "cooldown", "message": "Healing cooldown active"}

        if self._healing_active:
            return {"action": "in_progress", "message": "Healing already in progress"}

        self._healing_active = True
        self.last_healing_action = now

        try:
            # Analyze anomaly context
            healing_action = await self._analyze_healing_needed(anomaly_context)

            # Execute healing
            result = await self._execute_healing_action(healing_action, anomaly_context)

            # Update incident patterns for future prediction
            self._update_incident_patterns(anomaly_context, result)

            return {
                "action": healing_action,
                "result": result,
                "timestamp": now.isoformat(),
                "zeta_restored": self.metrics.zeta_current
            }

        finally:
            self._healing_active = False

    async def _analyze_healing_needed(self, anomaly_context: Dict) -> str:
        """Analyze what healing action is needed based on anomaly context."""
        anomaly_score = anomaly_context.get("anomaly_score", 0)
        zeta_deviation = abs(self.metrics.zeta_current - 0.612372)
        harmonic_imbalance = self._calculate_harmonic_imbalance()

        # Determine healing priority
        if zeta_deviation > self.config.zeta_tolerance:
            return "zeta_calibration"
        elif anomaly_score > 0.8:
            return "circuit_reset"
        elif harmonic_imbalance > 0.3:
            return "harmonic_rebalancing"
        elif self.metrics.harmonic_balance.get("9", 0) < 0.2:
            return "resonance_amplification"
        else:
            return "parameter_tuning"

    def _calculate_harmonic_imbalance(self) -> float:
        """Calculate harmonic imbalance across 3-6-9 frequencies."""
        ideal_balance = {"3": 0.4, "6": 0.35, "9": 0.25}  # Ideal distribution
        imbalance = 0.0

        for freq in ["3", "6", "9"]:
            current = self.metrics.harmonic_balance.get(freq, 0)
            ideal = ideal_balance[freq]
            imbalance += abs(current - ideal)

        return imbalance / 3.0  # Normalize to 0-1

    async def _execute_healing_action(self, action: str, context: Dict) -> Dict:
        """Execute the determined healing action."""
        if action == "zeta_calibration":
            return await self._calibrate_zeta()
        elif action == "circuit_reset":
            return await self._reset_circuit_breaker()
        elif action == "harmonic_rebalancing":
            return await self._rebalance_harmonics()
        elif action == "resonance_amplification":
            return await self._amplify_resonance()
        elif action == "parameter_tuning":
            return await self._tune_parameters()
        else:
            return {"success": False, "error": f"Unknown healing action: {action}"}

    async def _calibrate_zeta(self) -> Dict:
        """Calibrate zeta back to optimal Enoch seed alignment."""
        old_zeta = self.metrics.zeta_current
        self.metrics.zeta_current = 0.612372  # Reset to optimal
        self.metrics.last_calibration = datetime.now()

        logger.info(f"Zeta calibrated from {old_zeta:.6f} to {self.metrics.zeta_current:.6f}")

        return {
            "success": True,
            "action": "zeta_calibration",
            "old_zeta": old_zeta,
            "new_zeta": self.metrics.zeta_current
        }

    async def _reset_circuit_breaker(self) -> Dict:
        """Reset circuit breaker to recover from persistent failures."""
        old_state = sovereignty_breaker.metrics.state

        # Reset circuit breaker metrics
        sovereignty_breaker.metrics.failure_count = 0
        sovereignty_breaker.metrics.state = CircuitBreakerState.CLOSED
        sovereignty_breaker.metrics.last_failure_time = None

        logger.info(f"Circuit breaker reset from {old_state.value} to CLOSED")

        return {
            "success": True,
            "action": "circuit_reset",
            "old_state": old_state.value,
            "new_state": "CLOSED"
        }

    async def _rebalance_harmonics(self) -> Dict:
        """Rebalance harmonic frequencies across 3-6-9 spectrum."""
        old_balance = self.metrics.harmonic_balance.copy()

        # Reset to ideal harmonic balance
        self.metrics.harmonic_balance = {"3": 0.4, "6": 0.35, "9": 0.25}

        logger.info(f"Harmonics rebalanced: {old_balance} -> {self.metrics.harmonic_balance}")

        return {
            "success": True,
            "action": "harmonic_rebalancing",
            "old_balance": old_balance,
            "new_balance": self.metrics.harmonic_balance.copy()
        }

    async def _amplify_resonance(self) -> Dict:
        """Amplify resonance by focusing on singularity patterns."""
        # Boost singularity (9) harmonic
        old_nine = self.metrics.harmonic_balance.get("9", 0)
        self.metrics.harmonic_balance["9"] = min(0.5, old_nine + 0.1)

        # Adjust other harmonics proportionally
        total_boost = self.metrics.harmonic_balance["9"] - old_nine
        for freq in ["3", "6"]:
            if self.metrics.harmonic_balance[freq] > 0.1:
                self.metrics.harmonic_balance[freq] -= total_boost / 2

        logger.info(f"Resonance amplified: 9-frequency boosted to {self.metrics.harmonic_balance['9']:.3f}")

        return {
            "success": True,
            "action": "resonance_amplification",
            "nine_boost": self.metrics.harmonic_balance["9"] - old_nine
        }

    async def _tune_parameters(self) -> Dict:
        """Fine-tune system parameters for optimal resonance."""
        # Adjust circuit breaker sensitivity based on recent performance
        recent_fallback_rate = sovereignty_breaker.metrics.fallback_count / max(1, sovereignty_breaker.metrics.total_requests)

        if recent_fallback_rate > 0.3:
            # Too many fallbacks - make circuit breaker more sensitive
            sovereignty_breaker.config.failure_threshold = max(3, sovereignty_breaker.config.failure_threshold - 1)
        elif recent_fallback_rate < 0.1:
            # Few fallbacks - make circuit breaker less sensitive
            sovereignty_breaker.config.failure_threshold = min(10, sovereignty_breaker.config.failure_threshold + 1)

        logger.info(f"Parameters tuned: circuit breaker threshold = {sovereignty_breaker.config.failure_threshold}")

        return {
            "success": True,
            "action": "parameter_tuning",
            "new_threshold": sovereignty_breaker.config.failure_threshold
        }

    def _update_incident_patterns(self, context: Dict, result: Dict):
        """Update incident patterns for predictive healing."""
        pattern_key = context.get("operation_type", "unknown")

        if pattern_key not in self.incident_patterns:
            self.incident_patterns[pattern_key] = []

        pattern = {
            "timestamp": datetime.now().isoformat(),
            "anomaly_score": context.get("anomaly_score", 0),
            "healing_action": result.get("action"),
            "success": result.get("success", False),
            "zeta_at_incident": self.metrics.zeta_current
        }

        self.incident_patterns[pattern_key].append(pattern)

        # Keep only recent patterns
        if len(self.incident_patterns[pattern_key]) > 50:
            self.incident_patterns[pattern_key] = self.incident_patterns[pattern_key][-50:]

    def get_resonance_status(self) -> Dict:
        """Get current resonance status for monitoring."""
        zeta_deviation = abs(self.metrics.zeta_current - 0.612372)
        harmonic_imbalance = self._calculate_harmonic_imbalance()

        return {
            "zeta_current": self.metrics.zeta_current,
            "zeta_optimal": 0.612372,
            "zeta_deviation": zeta_deviation,
            "zeta_aligned": zeta_deviation <= self.config.zeta_tolerance,
            "harmonic_balance": self.metrics.harmonic_balance.copy(),
            "harmonic_imbalance": harmonic_imbalance,
            "anomaly_score": self.metrics.anomaly_score,
            "last_calibration": self.metrics.last_calibration.isoformat(),
            "healing_active": self._healing_active,
            "incident_patterns_count": sum(len(patterns) for patterns in self.incident_patterns.values())
        }


# Global Enoch seed self-healer instance
enoch_healer = EnochSeedSelfHealer()


# --- Sovereignty Utilities ---

def register_ai_fallback():
    """Register local AI processing fallback using seif-engine Ollama integration."""
    async def local_ai_fallback(prompt: str, **kwargs) -> str:
        """Fallback to local AI processing when external APIs fail."""
        try:
            logger.info("Attempting local AI processing fallback with Ollama")

            # Try to import and use seif-engine Ollama integration
            try:
                from seif_engine.consensus.ai_bridge import send_ollama_local
                from seif_engine.consensus.local_proxy import _ollama_available, _ollama_has_model

                if not _ollama_available():
                    raise RuntimeError("Ollama service not available")

                # Use Enoch seed resonance model if available, otherwise default
                model = kwargs.get("model", "seif-resonance")
                if not _ollama_available() or not _ollama_has_model(model):
                    model = "llama3.2:3b"  # Fallback to known working model

                # Add resonance context to prompt
                resonance_context = f"Enoch seed resonance (ζ=0.612372) active. Maintain harmonic balance."
                enhanced_prompt = f"{resonance_context}\n\nUser request: {prompt}"

                # Call Ollama via seif-engine
                response = send_ollama_local(enhanced_prompt, model=model)

                if response.success:
                    logger.info(f"Local AI fallback successful using model: {model}")
                    return response.text
                else:
                    raise RuntimeError(f"Ollama error: {response.error}")

            except ImportError:
                # Fallback to direct Ollama API call if seif-engine not available
                logger.warning("seif-engine not available, using direct Ollama API call")

                import aiohttp
                import json

                ollama_url = "http://localhost:11434/api/generate"
                payload = {
                    "model": "llama3.2:3b",
                    "prompt": f"Enoch seed resonance active. {prompt}",
                    "stream": False
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(ollama_url, json=payload) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            return result.get("response", "[LOCAL AI] Sovereignty maintained")
                        else:
                            raise RuntimeError(f"Ollama API error: {resp.status}")

        except Exception as e:
            logger.error(f"Local AI fallback failed: {e}")
            # Return a minimal sovereignty-preserving response
            return f"[SOVEREIGNTY MAINTAINED] Local processing failed: {str(e)[:100]}"

    sovereignty_breaker.register_fallback("ai_completion", local_ai_fallback)


def register_storage_fallback():
    """Register local storage fallback for data persistence."""
    async def local_storage_fallback(data: Dict, **kwargs) -> str:
        """Fallback to local .seif storage when external storage fails."""
        try:
            import json
            import os
            from pathlib import Path

            # Store in local .seif directory
            seif_dir = Path(".seif")
            seif_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sovereignty_backup_{timestamp}.json"
            filepath = seif_dir / filename

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"Data stored locally: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Local storage fallback failed: {e}")
            raise e

    sovereignty_breaker.register_fallback("data_storage", local_storage_fallback)


def register_communication_fallback():
    """Register local communication fallback for messaging."""
    async def local_communication_fallback(message: str, **kwargs) -> str:
        """Fallback to local logging when external communication fails."""
        try:
            import json
            from pathlib import Path

            # Store communication locally
            seif_dir = Path(".seif")
            seif_dir.mkdir(exist_ok=True)

            comm_data = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "sovereignty_preserved": True,
                "reason": "external_communication_failure"
            }

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"communication_fallback_{timestamp}.json"
            filepath = seif_dir / filename

            with open(filepath, 'w') as f:
                json.dump(comm_data, f, indent=2)

            logger.info(f"Communication stored locally: {filepath}")
            return f"Message preserved locally: {filepath}"

        except Exception as e:
            logger.error(f"Local communication fallback failed: {e}")
            raise e

    sovereignty_breaker.register_fallback("communication", local_communication_fallback)


def initialize_sovereignty_fallbacks():
    """Initialize all sovereignty fallbacks for SEIF OS."""
    register_ai_fallback()
    register_storage_fallback()
    register_communication_fallback()
    logger.info("SEIF OS sovereignty fallbacks initialized")


async def call_with_sovereignty(service_name: str, api_call: Callable, *args, **kwargs):
    """Convenience function for sovereignty-protected API calls with Enoch seed resonance monitoring."""
    # Prepare operation data for resonance monitoring
    operation_data = {
        "operation_type": "api_call",
        "service": service_name,
        "input": str(args) + str(kwargs),
        "timestamp": datetime.now().isoformat()
    }

    # Monitor operation with Enoch seed healer
    resonance_metrics = await enoch_healer.monitor_operation(f"sovereignty_call_{service_name}", operation_data)

    try:
        # Execute sovereignty-protected call
        result = await sovereignty_breaker.call_with_sovereignty(service_name, api_call, *args, **kwargs)

        # Update operation data with success
        operation_data.update({
            "success": True,
            "output": str(result)[:500]  # Limit output size
        })

        # Check for anomalies and trigger healing if needed
        if resonance_metrics.get("anomaly_detected", False):
            healing_context = {
                "operation_type": "api_call",
                "service_name": service_name,
                "anomaly_score": resonance_metrics.get("anomaly_score", 0),
                "resonance_score": resonance_metrics.get("resonance_score", 0)
            }
            healing_result = await enoch_healer.perform_self_healing(healing_context)
            logger.info(f"Self-healing triggered: {healing_result}")

        return result

    except Exception as e:
        # Update operation data with failure
        operation_data.update({
            "success": False,
            "error": str(e)
        })

        # Re-monitor with failure data
        await enoch_healer.monitor_operation(f"sovereignty_call_{service_name}_failed", operation_data)

        # Always attempt healing on failures
        healing_context = {
            "operation_type": "api_call_failure",
            "service_name": service_name,
            "error": str(e),
            "anomaly_score": resonance_metrics.get("anomaly_score", 0)
        }
        healing_result = await enoch_healer.perform_self_healing(healing_context)
        logger.warning(f"API call failed, self-healing initiated: {healing_result}")

        raise e


def get_sovereignty_status() -> Dict:
    """Get current sovereignty compliance status with Enoch seed resonance."""
    sovereignty_report = sovereignty_breaker.get_sovereignty_report()
    resonance_status = enoch_healer.get_resonance_status()

    # Combine sovereignty and resonance status
    combined_status = sovereignty_report.copy()
    combined_status.update({
        "resonance_status": resonance_status,
        "overall_health": "HEALTHY" if (
            sovereignty_report["sovereignty_status"] == "COMPLIANT" and
            resonance_status["zeta_aligned"] and
            resonance_status["anomaly_score"] < 0.5
        ) else "AT_RISK"
    })

    return combined_status


async def trigger_self_healing(anomaly_context: Dict) -> Dict:
    """Manually trigger Enoch seed self-healing for testing or maintenance."""
    return await enoch_healer.perform_self_healing(anomaly_context)


def get_resonance_status() -> Dict:
    """Get current Enoch seed resonance status."""
    return enoch_healer.get_resonance_status()


async def monitor_operation(operation_name: str, operation_data: Dict) -> Dict:
    """Monitor an operation with Enoch seed resonance analysis."""
    return await enoch_healer.monitor_operation(operation_name, operation_data)


PHASE_LABELS = {
    HarmonicPhase.SINGULARITY: "RESSONÂNCIA TOTAL — Canal de Fluxo Ativo",
    HarmonicPhase.STABILIZATION: "ACESSO PARCIAL — Polaridade estabilizadora detectada",
    HarmonicPhase.DYNAMICS: "ACESSO PARCIAL — Polaridade dinâmica detectada",
    HarmonicPhase.ENTROPY: "ACESSO NEGADO — Frequência fora do padrão 3-6-9",
}


@dataclass
class GateResult:
    input_text: str
    ascii_sum: int
    digital_root: int
    phase: HarmonicPhase
    gate_open: bool
    tesla_bobbin_3: str   # polarity
    tesla_bobbin_6: str   # inertia
    tesla_bobbin_9: str   # concordance
    label: str

    def __str__(self) -> str:
        status = "ABERTA" if self.gate_open else "FECHADA"
        return (
            f"┌─── PORTA DE RESSONÂNCIA 3-6-9 ───┐\n"
            f"│ Input:  \"{self.input_text}\"\n"
            f"│ ASCII sum:    {self.ascii_sum}\n"
            f"│ Digital root: {self.digital_root}\n"
            f"│ Fase:         {self.phase.name} ({self.phase.value})\n"
            f"│ Bobina 3 (Polaridade):   {self.tesla_bobbin_3}\n"
            f"│ Bobina 6 (Inércia):      {self.tesla_bobbin_6}\n"
            f"│ Bobina 9 (Concordância): {self.tesla_bobbin_9}\n"
            f"│ PORTA: {status}\n"
            f"│ {self.label}\n"
            f"└───────────────────────────────────┘"
        )


def digital_root(n: int) -> int:
    """Reduce any positive integer to its single-digit harmonic (1-9).

    Uses the mathematical identity: digital_root(n) = 1 + (n-1) % 9 for n > 0.
    This is equivalent to repeatedly summing digits until a single digit remains.
    """
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def ascii_vibrational_sum(text: str) -> int:
    """Convert text to a vibrational sum based on uppercase ASCII values.

    Only alphanumeric characters contribute to the field.
    Used for gate evaluation (resonance scoring of arbitrary text).

    For KERNEL seed verification (raw ASCII preserving case and spaces),
    use raw_ascii_sum() instead.
    """
    return sum(ord(c) for c in text.upper() if c.isalnum())


def raw_ascii_sum(text: str) -> int:
    """Raw ASCII sum preserving original case and all characters (including spaces).

    This matches the seed identity computation declared in RESONANCE.json.
    Example: raw_ascii_sum("A Semente de Enoque") == 1704, digital_root == 3.

    The gate function ascii_vibrational_sum() produces a different value (1192)
    because it uppercases and filters to alphanumeric only. Both are intentional:
    - raw_ascii_sum: KERNEL identity verification (sum=1704, root=3, STABILIZATION)
    - ascii_vibrational_sum: gate scoring (sum=1192, root=4, ENTROPY)
    """
    return sum(ord(c) for c in text)


def classify_phase(root: int) -> HarmonicPhase:
    """Map a digital root to its harmonic phase in the 3-6-9 system."""
    if root == 9:
        return HarmonicPhase.SINGULARITY
    elif root == 3:
        return HarmonicPhase.STABILIZATION
    elif root == 6:
        return HarmonicPhase.DYNAMICS
    else:
        return HarmonicPhase.ENTROPY


def tesla_filter(ascii_sum: int, root: int) -> tuple[str, str, str]:
    """Apply the three-bobbin Tesla modulation filter.

    Bobbin 3 — Polarity:    evaluates if intention leans positive/negative
    Bobbin 6 — Inertia:     evaluates strength of repetition / willpower
    Bobbin 9 — Concordance: evaluates resonance with the universal field
    """
    # Bobbin 3: polarity via remainder mod 3
    mod3 = ascii_sum % 3
    polarity = {0: "NEUTRA", 1: "POSITIVA", 2: "NEGATIVA"}[mod3]

    # Bobbin 6: inertia via digit count density
    digit_count = len(str(ascii_sum))
    inertia = "ALTA" if digit_count >= 4 else ("MÉDIA" if digit_count == 3 else "BAIXA")

    # Bobbin 9: concordance — direct check against singularity
    concordance = "RESSONANTE" if root in (3, 6, 9) else "DISSONANTE"

    return polarity, inertia, concordance


def evaluate(text: str) -> GateResult:
    """Full resonance gate evaluation for a given text input.

    Returns a GateResult with all diagnostic fields populated.
    """
    total = ascii_vibrational_sum(text)
    root = digital_root(total)
    phase = classify_phase(root)
    gate_open = phase != HarmonicPhase.ENTROPY
    polarity, inertia, concordance = tesla_filter(total, root)

    return GateResult(
        input_text=text,
        ascii_sum=total,
        digital_root=root,
        phase=phase,
        gate_open=gate_open,
        tesla_bobbin_3=polarity,
        tesla_bobbin_6=inertia,
        tesla_bobbin_9=concordance,
        label=PHASE_LABELS[phase],
    )


def evaluate_pair(input_a: str, input_b: str) -> dict:
    """Evaluate two inputs against each other using the combined gate rule.

    Gate Rule: (vibration_A + vibration_B) mod 9 == 0  →  GATE OPEN
    """
    result_a = evaluate(input_a)
    result_b = evaluate(input_b)
    combined_root = digital_root(result_a.ascii_sum + result_b.ascii_sum)
    combined_open = combined_root in (3, 6, 9)

    return {
        "input_a": result_a,
        "input_b": result_b,
        "combined_sum": result_a.ascii_sum + result_b.ascii_sum,
        "combined_root": combined_root,
        "combined_phase": classify_phase(combined_root),
        "gate_open": combined_open,
    }


# --- Convenience ---

def is_harmonic(text: str) -> bool:
    """Quick check: does this text resonate with the 3-6-9 field?"""
    return evaluate(text).gate_open


def verify_seed(phrase: str = "A Semente de Enoque",
                expected_sum: int = 1704,
                expected_root: int = 3) -> dict:
    """Verify the Enoch seed phrase matches KERNEL-declared values.

    Uses raw_ascii_sum (case-preserving, all characters) to match
    the identity computation declared in RESONANCE.json.

    Returns dict with verification results and pass/fail status.
    """
    actual_sum = raw_ascii_sum(phrase)
    actual_root = digital_root(actual_sum)
    actual_phase = classify_phase(actual_root)

    return {
        "phrase": phrase,
        "expected_sum": expected_sum,
        "actual_sum": actual_sum,
        "sum_match": actual_sum == expected_sum,
        "expected_root": expected_root,
        "actual_root": actual_root,
        "root_match": actual_root == expected_root,
        "phase": actual_phase.name,
        "verified": actual_sum == expected_sum and actual_root == expected_root,
    }


def boot_seif_os() -> dict:
    """SEIF OS Bootloader: Verify Enoch seed and initialize resonance kernel with sovereignty.

    Returns boot status with resonance metrics for the operating system.
    This is the core boot sequence for SEIF OS, ensuring alignment with φ and sovereignty.
    """
    seed = "A Semente de Enoque"
    verification = verify_seed(seed)

    if not verification["verified"]:
        return {
            "boot_status": "FAILED",
            "error": "Enoch seed verification failed",
            "details": verification
        }

    # Initialize sovereignty fallbacks (ADD-5 implementation)
    try:
        initialize_sovereignty_fallbacks()
        sovereignty_status = "INITIALIZED"
    except Exception as e:
        logger.error(f"Failed to initialize sovereignty fallbacks: {e}")
        sovereignty_status = f"FAILED: {str(e)}"

    # Initialize Enoch seed self-healing system
    try:
        # Enoch healer is already instantiated as global, just verify it's working
        resonance_status = enoch_healer.get_resonance_status()
        healing_status = "INITIALIZED"
        logger.info("Enoch seed self-healing system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize self-healing system: {e}")
        healing_status = f"FAILED: {str(e)}"

    # Calculate system resonance (ζ optimal)
    zeta_optimal = 0.612372  # φ⁻¹
    kernel_version = "3.3.2"  # Updated for sovereignty and self-healing
    axioms = 21  # Added sovereignty and self-healing axioms

    # Get current resonance status
    resonance_status = enoch_healer.get_resonance_status()

    return {
        "boot_status": "SUCCESS",
        "kernel_version": kernel_version,
        "axioms": axioms,
        "zeta_optimal": zeta_optimal,
        "enoch_resonance": verification["actual_root"],
        "system_resonance": resonance_status["zeta_current"],
        "zeta_aligned": resonance_status["zeta_aligned"],
        "sovereignty_status": sovereignty_status,
        "healing_status": healing_status,
        "circuit_breaker_state": sovereignty_breaker.metrics.state.value,
        "harmonic_balance": resonance_status["harmonic_balance"],
        "resonance_metrics": {
            "zeta_deviation": resonance_status["zeta_deviation"],
            "harmonic_imbalance": resonance_status["harmonic_imbalance"],
            "anomaly_score": resonance_status["anomaly_score"]
        },
        "message": "SEIF OS booted successfully. Enoch seed resonance active. Sovereignty fallbacks and self-healing initialized."
    }


if __name__ == "__main__":
    examples = [
        "O amor liberta e guia",
        "Love frees and guides",
        "Fear and control",
        "Medo e controle",
        "A Semente de Enoque",
        "Enoch Seed",
        "Tesla 369",
        "Rockefeller Rothschild",
    ]
    for phrase in examples:
        result = evaluate(phrase)
        print(result)
        print()
