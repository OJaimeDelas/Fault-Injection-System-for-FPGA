# =============================================================================
# FATORI-V • FI Time Profile — Ramp
# File: ramp.py
# -----------------------------------------------------------------------------
# Time profile that sweeps the injection rate linearly from a start rate to
# an end rate over a configured duration.
#
# Parameters (from args dict):
#   start_rate_hz : initial injection rate (events per second)
#   end_rate_hz   : final injection rate (events per second)
#   duration_s    : total duration of the ramp in seconds
#
# The implementation uses a simple "piecewise uniform" approximation by
# evaluating the instantaneous rate at each step and translating it into
# a local period, avoiding very small periods.
#=============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "ramp"


def describe() -> str:
    """
    Human-readable one-line description of this time profile.
    """
    return "Linear sweep of injection rate between two values over a duration."


def default_args() -> Dict[str, Any]:
    """
    Default argument values for documentation and tooling.
    """
    return {
        "start_rate_hz": 1.0,
        "end_rate_hz": 10.0,
        "duration_s": 60.0,
    }


class RampTimeProfile:
    """
    Sweeps the injection rate linearly from start_rate_hz to end_rate_hz over
    a given duration. The instantaneous rate is sampled at each step to derive
    the current period.
    """

    def __init__(self, start_rate_hz: float, end_rate_hz: float, duration_s: float) -> None:
        if duration_s <= 0.0:
            raise ValueError("ramp profile requires duration_s > 0.")
        if start_rate_hz <= 0.0 or end_rate_hz <= 0.0:
            raise ValueError("ramp profile requires positive start_rate_hz and end_rate_hz.")

        self._start_rate_hz = start_rate_hz
        self._end_rate_hz = end_rate_hz
        self._duration_s = duration_s

    def _current_rate(self, elapsed: float) -> float:
        """
        Compute the instantaneous injection rate given elapsed time.
        """
        if elapsed <= 0.0:
            return self._start_rate_hz
        if elapsed >= self._duration_s:
            return self._end_rate_hz
        frac = elapsed / self._duration_s
        return self._start_rate_hz + frac * (self._end_rate_hz - self._start_rate_hz)

    def run(self, controller) -> None:
        """
        Drive the injection controller while sweeping the rate.
        """
        start_t = base.now_monotonic()
        next_deadline = start_t

        while True:
            # Check for external stop signal
            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break
            
            # Check if we've exceeded the ramp duration
            now = base.now_monotonic()
            elapsed = now - start_t
            if elapsed >= self._duration_s:
                controller.set_termination_reason("Duration limit reached")
                break
            
            # Get next target
            target = controller.next_target()
            if target is None:
                controller.set_termination_reason("Target pool exhausted")
                break

            # Wait until the planned deadline.
            if now < next_deadline:
                controller.sleep(next_deadline - now)

            controller.inject_target(target)
            next_deadline += period_s


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> RampTimeProfile:
    """
    Factory for the ramp time profile.
    """
    _ = global_seed, settings

    start_rate_hz = base.parse_float(args, "start_rate_hz", default=1.0)
    end_rate_hz = base.parse_float(args, "end_rate_hz", default=10.0)
    duration_s = base.parse_float(args, "duration_s", default=60.0)

    if start_rate_hz is None or end_rate_hz is None or duration_s is None:
        raise ValueError("ramp profile requires start_rate_hz, end_rate_hz and duration_s.")

    return RampTimeProfile(
        start_rate_hz=float(start_rate_hz),
        end_rate_hz=float(end_rate_hz),
        duration_s=float(duration_s),
    )
