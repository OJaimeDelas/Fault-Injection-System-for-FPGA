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
#                controller requests a stop or the target pool is exhausted.
#   seed       : optional local seed for reproducible timing; if omitted, the
#                engine's global_seed is used.
#=============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "poisson"


def describe() -> str:
    return "Poisson process with exponential inter-arrival times at a fixed rate."


def default_args() -> Dict[str, Any]:
    return {
        "rate_hz": 1.0,
        "duration_s": None,
        "seed": None,
    }


class PoissonTimeProfile:
    """
    Drives injections with exponential inter-arrival times at a constant rate.
    """

    def __init__(self, rate_hz: float, duration_s: Optional[float], rng) -> None:
        if rate_hz <= 0.0:
            raise ValueError("poisson profile requires rate_hz > 0.")
        self._rate_hz = rate_hz
        self._duration_s = duration_s
        self._rng = rng

    def run(self, controller) -> None:
        start_t = base.now_monotonic()

        while True:
            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break

            now = base.now_monotonic()
            if self._duration_s is not None and (now - start_t) >= self._duration_s:
                controller.set_termination_reason("Duration limit reached")
                break

            # Sample the next inter-arrival time and compute an absolute deadline.
            delta_t = base.sample_exponential(self._rng, self._rate_hz)
            deadline = now + delta_t

            # If the next scheduled event would occur beyond duration_s, stop.
            if self._duration_s is not None and (deadline - start_t) >= self._duration_s:
                controller.set_termination_reason("Duration limit reached")
                break

            target = controller.next_target()
            if target is None:
                controller.set_termination_reason("Target pool exhausted")
                break

            delay = deadline - base.now_monotonic()
            if delay > 0.0:
                controller.sleep(delay)

            controller.inject_target(target)


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> PoissonTimeProfile:
    _ = settings

    rate_hz = base.parse_float(args, "rate_hz", default=None)
    duration_s = base.parse_float(args, "duration_s", default=None)
    seed_str = args.get("seed")

    if rate_hz is None:
        raise ValueError("poisson profile requires rate_hz.")

    rng = base.make_rng(global_seed, seed_str)
    return PoissonTimeProfile(rate_hz=float(rate_hz), duration_s=duration_s, rng=rng)
