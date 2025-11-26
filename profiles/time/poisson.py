# =============================================================================
# FATORI-V • FI Time Profile — Poisson
# File: poisson.py
# -----------------------------------------------------------------------------
# Time profile that drives injections according to a Poisson process, using
# exponential inter-arrival times with a constant rate.
#
# Parameters (from args dict):
#   rate_hz    : average injections per second (float, required)
#   duration_s : optional stop time in seconds; if omitted, runs until the
#                controller requests a stop or the area profile is exhausted.
#   seed       : optional local seed for reproducible timing; if omitted, the
#                engine's global_seed is used.
#=============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "poisson"


def describe() -> str:
    """
    Human-readable one-line description of this time profile.
    """
    return "Poisson process with exponential inter-arrival times at a fixed rate."


def default_args() -> Dict[str, Any]:
    """
    Default argument values for documentation and tooling.
    """
    return {
        "rate_hz": 1.0,
        "duration_s": None,
        "seed": None,
    }


class PoissonTimeProfile:
    """
    Generates exponential inter-arrival times for injections at a constant
    average rate.
    """

    def __init__(self, rate_hz: float, duration_s: Optional[float], rng) -> None:
        if rate_hz <= 0.0:
            raise ValueError("poisson profile requires rate_hz > 0.")
        self._rate_hz = rate_hz
        self._duration_s = duration_s
        self._rng = rng

    def run(self, controller) -> None:
        """
        Drive the injection controller using exponential inter-arrival spacing.
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

            # Draw a random inter-arrival time.
            delta_t = base.sample_exponential(self._rng, self._rate_hz)
            current_t += delta_t

            # Obtain next target.
            target = controller.next_target()
            if target is None:
                break

            now = base.now_monotonic()
            delay = current_t - now
            if delay > 0.0:
                controller.sleep(delay)

            controller.inject_target(target)


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> PoissonTimeProfile:
    """
    Factory for the Poisson time profile.
    """
    _ = settings

    rate_hz = base.parse_float(args, "rate_hz", default=None)
    duration_s = base.parse_float(args, "duration_s", default=None)
    seed_str = args.get("seed")

    if rate_hz is None:
        raise ValueError("poisson profile requires rate_hz.")

    rng = base.make_rng(global_seed, seed_str)
    return PoissonTimeProfile(rate_hz=float(rate_hz), duration_s=duration_s, rng=rng)
