# =============================================================================
# FATORI-V • FI Time Profile — MMPP2 (Two-State Bursty Poisson)
# File: mmpp2.py
# -----------------------------------------------------------------------------
# Time profile implementing a two-state Markov-modulated Poisson process.
#
# The process alternates between:
#   - state 0: low-rate Poisson process
#   - state 1: high-rate Poisson process
#
# After each injection, a state transition may occur according to the given
# transition probabilities.
#
# Parameters (from args dict):
#   low_hz           : Poisson rate in LOW state (float, required)
#   high_hz          : Poisson rate in HIGH state (float, required)
#   p_low_to_high    : Probability [0,1] to switch LOW→HIGH after a shot (float, required)
#   p_high_to_low    : Probability [0,1] to switch HIGH→LOW after a shot (float, required)
#   start_state      : Initial state: "low" or "high" (string, default "low")
#   duration_s       : Optional stop time in seconds
#   seed             : Optional local seed; if omitted, global_seed is used
#=============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "mmpp2"


def describe() -> str:
    """
    Human-readable one-line description of this time profile.
    """
    return "Two-state Markov-modulated Poisson process (bursty traffic)."


def default_args() -> Dict[str, Any]:
    """
    Default argument values for documentation and tooling.
    """
    return {
        "low_hz": 1.0,
        "high_hz": 10.0,
        "p_low_to_high": 0.05,
        "p_high_to_low": 0.05,
        "start_state": "low",
        "duration_s": None,
        "seed": None,
    }


class MMPP2TimeProfile:
    """
    Two-state Markov-modulated Poisson process.

    LOW state uses low_hz, HIGH state uses high_hz. After each injection, the
    process may transition between states using probabilities p_low_to_high 
    and p_high_to_low.
    """

    def __init__(
        self,
        low_hz: float,
        high_hz: float,
        p_low_to_high: float,
        p_high_to_low: float,
        start_state: str,
        duration_s: Optional[float],
        rng,
    ) -> None:
        if low_hz <= 0.0 or high_hz <= 0.0:
            raise ValueError("mmpp2 profile requires positive rates.")
        if not (0.0 <= p_low_to_high <= 1.0 and 0.0 <= p_high_to_low <= 1.0):
            raise ValueError("mmpp2 profile requires 0 <= p_low_to_high, p_high_to_low <= 1.")
        if start_state not in ("low", "high"):
            raise ValueError("mmpp2 profile requires start_state to be 'low' or 'high'.")

        self._low_hz = low_hz
        self._high_hz = high_hz
        self._p_low_to_high = p_low_to_high
        self._p_high_to_low = p_high_to_low
        self._duration_s = duration_s
        self._rng = rng

        # Start in the specified state
        self._state = start_state

    def _current_rate(self) -> float:
        """
        Return the rate for the current state.
        """
        return self._low_hz if self._state == "low" else self._high_hz

    def _maybe_transition(self) -> None:
        """
        Transition between states according to p_low_to_high/p_high_to_low.
        """
        u = self._rng.random()
        if self._state == "low":
            if u < self._p_low_to_high:
                self._state = "high"
        else:
            if u < self._p_high_to_low:
                self._state = "low"

    def run(self, controller) -> None:
        """
        Drive the injection controller using a two-state bursty Poisson model.
        """
        start_t = base.now_monotonic()
        current_t = start_t

        while True:
            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break

            if self._duration_s is not None:
                elapsed = current_t - start_t
                if elapsed >= self._duration_s:
                    controller.set_termination_reason("Duration limit reached")
                    break

            # Draw inter-arrival time based on the current state's rate.
            rate_hz = self._current_rate()
            delta_t = base.sample_exponential(self._rng, rate_hz)
            current_t += delta_t

            target = controller.next_target()
            if target is None:
                controller.set_termination_reason("Target pool exhausted")
                break

            now = base.now_monotonic()
            delay = current_t - now
            if delay > 0.0:
                controller.sleep(delay)

            controller.inject_target(target)

            # After each injection, decide whether to switch state.
            self._maybe_transition()


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> MMPP2TimeProfile:
    """
    Factory for the MMPP2 time profile.
    """
    _ = settings

    low_hz = base.parse_float(args, "low_hz", default=None)
    high_hz = base.parse_float(args, "high_hz", default=None)
    p_low_to_high = base.parse_float(args, "p_low_to_high", default=None)
    p_high_to_low = base.parse_float(args, "p_high_to_low", default=None)
    start_state = args.get("start_state", "low").strip().lower()
    duration_s = base.parse_float(args, "duration_s", default=None)
    seed_str = args.get("seed")

    if low_hz is None or high_hz is None or p_low_to_high is None or p_high_to_low is None:
        raise ValueError("mmpp2 profile requires low_hz, high_hz, p_low_to_high and p_high_to_low.")

    rng = base.make_rng(global_seed, seed_str)
    return MMPP2TimeProfile(
        low_hz=float(low_hz),
        high_hz=float(high_hz),
        p_low_to_high=float(p_low_to_high),
        p_high_to_low=float(p_high_to_low),
        start_state=start_state,
        duration_s=duration_s,
        rng=rng,
    )
