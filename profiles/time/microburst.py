# =============================================================================
# FATORI-V • FI Time Profile — Microburst
# File: microburst.py
# -----------------------------------------------------------------------------
# Time profile that alternates between idle periods and short high-rate burst
# periods, using FIXED-RATE (uniform) spacing in both intervals.
#
# Parameters (from args dict):
#   burst_rate_hz    : Injection rate during burst periods (float > 0, required)
#   idle_rate_hz     : Injection rate during idle periods (float >= 0, default 0)
#   burst_duration_s : Duration of each burst period in seconds (float > 0, required)
#   idle_duration_s  : Duration of each idle period in seconds (float > 0, required)
#   bursts           : Number of bursts to execute (int > 0, optional)
#   duration_s       : Overall time limit in seconds (float > 0, optional)
#   seed             : Accepted for CLI compatibility; unused (schedule is deterministic)
#
# If both 'bursts' and 'duration_s' are set, whichever occurs first ends the profile.
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "microburst"


def describe() -> str:
    return "Alternating idle and burst periods with fixed-rate spacing."


def default_args() -> Dict[str, Any]:
    return {
        "burst_rate_hz": 5.0,
        "idle_rate_hz": 0.0,
        "burst_duration_s": 1.0,
        "idle_duration_s": 2.0,
        "bursts": None,
        "duration_s": None,
        "seed": None,  # accepted but unused
    }


class MicroburstTimeProfile:
    """
    Alternates between idle and burst periods. Each interval uses uniform
    spacing at its configured rate.
    """

    def __init__(
        self,
        burst_rate_hz: float,
        idle_rate_hz: float,
        burst_duration_s: float,
        idle_duration_s: float,
        bursts: Optional[int],
        duration_s: Optional[float],
    ) -> None:
        if idle_duration_s <= 0.0 or burst_duration_s <= 0.0:
            raise ValueError("microburst profile requires positive durations.")
        if burst_rate_hz <= 0.0:
            raise ValueError("microburst profile requires burst_rate_hz > 0.")
        if idle_rate_hz < 0.0:
            raise ValueError("microburst profile requires idle_rate_hz >= 0.")
        if bursts is not None and bursts <= 0:
            raise ValueError("microburst profile requires bursts > 0 if specified.")
        if duration_s is not None and duration_s <= 0.0:
            raise ValueError("microburst profile requires duration_s > 0 if specified.")

        self._burst_rate_hz = float(burst_rate_hz)
        self._idle_rate_hz = float(idle_rate_hz)
        self._burst_duration_s = float(burst_duration_s)
        self._idle_duration_s = float(idle_duration_s)
        self._bursts = bursts
        self._duration_s = duration_s

    def _run_interval(self, controller, rate_hz: float, duration_s: float) -> bool:
        """
        Run a single interval (idle or burst) with a fixed rate and duration.

        Returns False if the controller requested a stop or the target pool
        exhausted targets; True otherwise.
        """
        start_t = base.now_monotonic()
        end_t = start_t + duration_s

        if rate_hz <= 0.0:
            # No injections; sleep to interval end in coarse steps.
            while True:
                if controller.should_stop():
                    return False
                now = base.now_monotonic()
                if now >= end_t:
                    return True
                controller.sleep(min(1.0, end_t - now))

        period_s = 1.0 / rate_hz
        inj_count = 0

        while True:
            if controller.should_stop():
                return False

            target_time = start_t + (inj_count * period_s)
            if target_time >= end_t:
                return True

            target = controller.next_target()
            if target is None:
                return False

            now = base.now_monotonic()
            sleep_s = target_time - now
            if sleep_s > 0.0:
                controller.sleep(sleep_s)

            controller.inject_target(target)
            inj_count += 1

    def run(self, controller) -> None:
        campaign_start = base.now_monotonic()
        burst_count = 0

        while True:
            if self._bursts is not None and burst_count >= self._bursts:
                controller.set_termination_reason("Requested number of bursts completed")
                break

            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break

            if self._duration_s is not None:
                elapsed = base.now_monotonic() - campaign_start
                if elapsed >= self._duration_s:
                    controller.set_termination_reason("Duration limit reached")
                    break
                remaining = self._duration_s - elapsed
            else:
                remaining = None

            # Idle interval (possibly truncated by remaining duration).
            idle_len = self._idle_duration_s if remaining is None else min(self._idle_duration_s, remaining)
            if idle_len > 0.0:
                ok = self._run_interval(controller, self._idle_rate_hz, idle_len)
                if not ok:
                    if controller.should_stop():
                        controller.set_termination_reason("Stop requested")
                    else:
                        controller.set_termination_reason("Target pool exhausted")
                    break

            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break

            if self._duration_s is not None:
                elapsed = base.now_monotonic() - campaign_start
                if elapsed >= self._duration_s:
                    controller.set_termination_reason("Duration limit reached")
                    break
                remaining = self._duration_s - elapsed
            else:
                remaining = None

            # Burst interval (possibly truncated by remaining duration).
            burst_len = self._burst_duration_s if remaining is None else min(self._burst_duration_s, remaining)
            if burst_len > 0.0:
                ok = self._run_interval(controller, self._burst_rate_hz, burst_len)
                if not ok:
                    if controller.should_stop():
                        controller.set_termination_reason("Stop requested")
                    else:
                        controller.set_termination_reason("Target pool exhausted")
                    break

            burst_count += 1


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> MicroburstTimeProfile:
    _ = global_seed, settings

    burst_rate_hz = base.parse_float(args, "burst_rate_hz", default=None)
    idle_rate_hz = base.parse_float(args, "idle_rate_hz", default=0.0)
    burst_duration_s = base.parse_float(args, "burst_duration_s", default=None)
    idle_duration_s = base.parse_float(args, "idle_duration_s", default=None)
    bursts = base.parse_int(args, "bursts", default=None)
    duration_s = base.parse_float(args, "duration_s", default=None)

    # Accepted for CLI compatibility; unused for deterministic spacing.
    _ = args.get("seed")

    if burst_rate_hz is None or burst_duration_s is None or idle_duration_s is None:
        raise ValueError("microburst profile requires burst_rate_hz, burst_duration_s and idle_duration_s.")

    return MicroburstTimeProfile(
        burst_rate_hz=float(burst_rate_hz),
        idle_rate_hz=float(idle_rate_hz or 0.0),
        burst_duration_s=float(burst_duration_s),
        idle_duration_s=float(idle_duration_s),
        bursts=bursts,
        duration_s=duration_s,
    )
