# =============================================================================
# FATORI-V • FI Time Profile — Uniform
# File: uniform.py
# -----------------------------------------------------------------------------
# Time profile that fires injections at a constant cadence.
#
# Parameters (from args dict):
#   rate_hz    : injections per second (float)
#   period_s   : period between injections (float); overrides rate_hz if set
#   duration_s : optional stop time in seconds; if omitted, runs until
#                the controller requests a stop or the area profile is
#                exhausted.
#
# At each step:
#   - wait until the next deadline,
#   - request the next target from the controller,
#   - inject the target if available,
#   - stop when there are no more targets or when duration is exceeded.
#=============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "uniform"


def describe() -> str:
    """
    Human-readable one-line description of this time profile.
    """
    return "Uniform injection cadence (constant period or rate)."


def default_args() -> Dict[str, Any]:
    """
    Default argument values for documentation and tooling.
    """
    return {
        "rate_hz": 1.0,
        "period_s": None,
        "duration_s": None,
    }


class UniformTimeProfile:
    """
    Drives injections at a fixed rate or fixed period until an optional
    duration is reached or no further targets are available.
    """

    def __init__(self, rate_hz: Optional[float], period_s: Optional[float], duration_s: Optional[float]) -> None:
        # Resolve effective period from rate or period, preferring period_s.
        if period_s is not None and period_s > 0.0:
            self._period_s = period_s
        elif rate_hz is not None and rate_hz > 0.0:
            self._period_s = 1.0 / rate_hz
        else:
            raise ValueError("uniform profile requires positive rate_hz or period_s.")

        self._duration_s = duration_s

    def run(self, controller) -> None:
        """
        Drive the injection controller with a fixed inter-injection interval.
        """
        start_t = base.now_monotonic()
        next_deadline = start_t

        while True:
            # Check for external stop request (e.g. from the engine).
            if controller.should_stop():
                break

            # Stop if a duration limit is configured and reached.
            if self._duration_s is not None:
                elapsed = base.now_monotonic() - start_t
                if elapsed >= self._duration_s:
                    break

            # Request the next target to inject.
            target = controller.next_target()
            if target is None:
                # No more targets available from pool or area profile.
                break

            # Schedule the next injection time.
            now = base.now_monotonic()
            if now < next_deadline:
                controller.sleep(next_deadline - now)
            else:
                # No sleep if we are already past the planned deadline.
                pass

            # Inject the target. Failures are handled inside the controller
            # (logging, stop flags) so this method does not inspect the result.
            controller.inject_target(target)

            # Move to the next deadline.
            next_deadline += self._period_s


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,  # unused; kept for a uniform factory signature
) -> UniformTimeProfile:
    """
    Factory for the uniform time profile.

    args:
        Parsed "k=v" dictionary from the CLI or higher-level tools.
    global_seed:
        Present for interface symmetry but not used here.
    settings:
        fi_settings module, available for profiles that require global
        configuration; unused here.
    """
    _ = global_seed, settings  # silence unused-variable warnings

    rate_hz = base.parse_float(args, "rate_hz", default=None)
    period_s = base.parse_float(args, "period_s", default=None)
    duration_s = base.parse_float(args, "duration_s", default=None)

    return UniformTimeProfile(rate_hz=rate_hz, period_s=period_s, duration_s=duration_s)
