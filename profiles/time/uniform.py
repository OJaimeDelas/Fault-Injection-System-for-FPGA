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
# Timing Strategy:
#   Uses absolute deadline tracking to prevent drift accumulation.
#   Each injection is scheduled at: start_time + (injection_count * period)
#   This ensures that execution time variations don't cause cumulative drift.
#
# Accuracy:
#   At high rates (>10Hz), Python's time.sleep() precision becomes a factor.
#   For best accuracy at high rates, use short periods and ensure the system
#   has low scheduling latency.
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
    
    Uses absolute deadline tracking to minimize cumulative drift from
    execution time variations. Each injection is scheduled independently
    from campaign start time rather than relative to previous injection.
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
        
        Timing is based on absolute deadlines calculated from campaign start
        to prevent drift accumulation. Each injection N is scheduled at:
        start_time + N * period
        
        This ensures that variations in execution time don't cause the
        injection rate to drift over time.
        """
        # Record campaign start time for absolute deadline calculation
        start_t = base.now_monotonic()
        
        # Track number of injections for deadline calculation
        injection_count = 0
        

        while True:
            # Check for external stop signal (e.g., from benchmark sync)
            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break

            # Check optional duration limit
            if self._duration_s is not None:
                elapsed = base.now_monotonic() - start_t
                if elapsed >= self._duration_s:
                    controller.set_termination_reason("Duration limit reached")
                    break

            # Request the next target to inject.
            target = controller.next_target()
            if target is None:
                # No more targets available from pool or area profile.
                controller.set_termination_reason("Target pool exhausted")
                break

            # Calculate absolute deadline for this injection.
            # Using absolute deadlines prevents drift accumulation.
            target_time = start_t + (injection_count * self._period_s)
            
            # Sleep until target time if we're ahead of schedule.
            now = base.now_monotonic()
            sleep_duration = target_time - now

            
            if sleep_duration > 0:
                # We're ahead of schedule - sleep until target time
                controller.sleep(sleep_duration)
            # If sleep_duration <= 0, we're behind schedule - inject immediately
            # without sleeping. This happens when execution time exceeds period.

            # Inject the target. Failures are handled inside the controller
            # (logging, stop flags) so this method does not inspect the result.
            controller.inject_target(target)

            # Increment injection counter for next deadline calculation
            injection_count += 1


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