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
#   rate0_hz : Poisson rate in state 0 (float, required)
#   rate1_hz : Poisson rate in state 1 (float, required)
#   p01      : probability of jumping 0 -> 1 after an event (0..1, required)
#   p10      : probability of jumping 1 -> 0 after an event (0..1, required)
#   duration_s : optional stop time in seconds
#   seed     : optional local seed; if omitted, global_seed is used
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
        "rate0_hz": 1.0,
        "rate1_hz": 10.0,
        "p01": 0.1,
        "p10": 0.1,
        "duration_s": None,
        "seed": None,
    }


class MMPP2TimeProfile:
    """
    Two-state Markov-modulated Poisson process.

    State 0 uses rate0_hz, state 1 uses rate1_hz. After each injection, the
    process may transition between states using probabilities p01 and p10.
    """

    def __init__(
        self,
        rate0_hz: float,
        rate1_hz: float,
        p01: float,
        p10: float,
        duration_s: Optional[float],
        rng,
    ) -> None:
        if rate0_hz <= 0.0 or rate1_hz <= 0.0:
            raise ValueError("mmpp2 profile requires positive rates.")
        if not (0.0 <= p01 <= 1.0 and 0.0 <= p10 <= 1.0):
            raise ValueError("mmpp2 profile requires 0 <= p01,p10 <= 1.")

        self._rate0_hz = rate0_hz
        self._rate1_hz = rate1_hz
        self._p01 = p01
        self._p10 = p10
        self._duration_s = duration_s
        self._rng = rng

        # Start in state 0 by default.
        self._state = 0

    def _current_rate(self) -> float:
        """
        Return the rate for the current state.
        """
        return self._rate0_hz if self._state == 0 else self._rate1_hz

    def _maybe_transition(self) -> None:
        """
        Transition between states according to p01/p10.
        """
        u = self._rng.random()
        if self._state == 0:
            if u < self._p01:
                self._state = 1
        else:
            if u < self._p10:
                self._state = 0

    def run(self, controller) -> None:
        """
        Drive the injection controller using a two-state bursty Poisson model.
        """
        start_t = base.now_monotonic()
        current_t = start_t

        while True:
            if controller.should_stop():
                break

            if self._duration_s is not None:
                elapsed = current_t - start_t
                if elapsed >= self._duration_s:
                    break

            # Draw inter-arrival time based on the current state's rate.
            rate_hz = self._current_rate()
            delta_t = base.sample_exponential(self._rng, rate_hz)
            current_t += delta_t

            target = controller.next_target()
            if target is None:
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

    rate0_hz = base.parse_float(args, "rate0_hz", default=None)
    rate1_hz = base.parse_float(args, "rate1_hz", default=None)
    p01 = base.parse_float(args, "p01", default=None)
    p10 = base.parse_float(args, "p10", default=None)
    duration_s = base.parse_float(args, "duration_s", default=None)
    seed_str = args.get("seed")

    if rate0_hz is None or rate1_hz is None or p01 is None or p10 is None:
        raise ValueError("mmpp2 profile requires rate0_hz, rate1_hz, p01 and p10.")

    rng = base.make_rng(global_seed, seed_str)
    return MMPP2TimeProfile(
        rate0_hz=float(rate0_hz),
        rate1_hz=float(rate1_hz),
        p01=float(p01),
        p10=float(p10),
        duration_s=duration_s,
        rng=rng,
    )
