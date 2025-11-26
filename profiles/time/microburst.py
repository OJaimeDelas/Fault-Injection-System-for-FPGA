# =============================================================================
# FATORI-V • FI Time Profile — Microburst
# File: microburst.py
# -----------------------------------------------------------------------------
# Time profile that alternates between idle periods and short high-rate burst
# periods, useful for stressing systems with clustered injections.
#
# Parameters (from args dict):
#   idle_rate_hz   : Poisson rate during idle periods (float, >= 0)
#   idle_duration_s: duration of each idle period in seconds (float > 0)
#   burst_rate_hz  : Poisson rate during burst periods (float > 0)
#   burst_duration_s: duration of each burst period in seconds (float > 0)
#   cycles         : number of idle+burst cycles to execute (int, > 0)
#   seed           : optional local seed; if omitted, global_seed is used
#=============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "microburst"


def describe() -> str:
    """
    Human-readable one-line description of this time profile.
    """
    return "Alternating idle and high-rate burst periods with Poisson spacing."


def default_args() -> Dict[str, Any]:
    """
    Default argument values for documentation and tooling.
    """
    return {
        "idle_rate_hz": 0.1,
        "idle_duration_s": 10.0,
        "burst_rate_hz": 20.0,
        "burst_duration_s": 1.0,
        "cycles": 10,
        "seed": None,
    }


class MicroburstTimeProfile:
    """
    Alternates between idle and burst periods, each modelled as a Poisson
    process with its own rate and duration.
    """

    def __init__(
        self,
        idle_rate_hz: float,
        idle_duration_s: float,
        burst_rate_hz: float,
        burst_duration_s: float,
        cycles: int,
        rng,
    ) -> None:
        if idle_duration_s <= 0.0 or burst_duration_s <= 0.0:
            raise ValueError("microburst profile requires positive durations.")
        if burst_rate_hz <= 0.0:
            raise ValueError("microburst profile requires burst_rate_hz > 0.")
        if cycles <= 0:
            raise ValueError("microburst profile requires cycles > 0.")

        self._idle_rate_hz = max(idle_rate_hz, 0.0)
        self._idle_duration_s = idle_duration_s
        self._burst_rate_hz = burst_rate_hz
        self._burst_duration_s = burst_duration_s
        self._cycles = cycles
        self._rng = rng

    def _run_interval(self, controller, rate_hz: float, duration_s: float) -> bool:
        """
        Run a single interval (idle or burst) with a fixed rate and duration.

        Returns False if the controller requested a stop or the area profile
        exhausted targets; True otherwise.
        """
        start_t = base.now_monotonic()
        current_t = start_t

        # During idle intervals with rate 0, no injections are fired.
        if rate_hz <= 0.0:
            while True:
                if controller.should_stop():
                    return False
                elapsed = base.now_monotonic() - start_t
                if elapsed >= duration_s:
                    break
                # Sleep in coarse steps during idle.
                controller.sleep(min(1.0, duration_s - elapsed))
            return True

        # Active interval with Poisson spacing.
        while True:
            if controller.should_stop():
                return False
            now = base.now_monotonic()
            elapsed = now - start_t
            if elapsed >= duration_s:
                # Interval finished.
                return True

            # Draw next inter-arrival and schedule injection.
            delta_t = base.sample_exponential(self._rng, rate_hz)
            current_t = now + delta_t
            if current_t - start_t > duration_s:
                # Next event would fall beyond the interval; finish.
                return True

            target = controller.next_target()
            if target is None:
                return False

            delay = current_t - base.now_monotonic()
            if delay > 0.0:
                controller.sleep(delay)

            controller.inject_target(target)

    def run(self, controller) -> None:
        """
        Execute the configured number of idle+burst cycles.
        """
        for _ in range(self._cycles):
            if controller.should_stop():
                break
            # Idle interval
            if not self._run_interval(controller, self._idle_rate_hz, self._idle_duration_s):
                break
            if controller.should_stop():
                break
            # Burst interval
            if not self._run_interval(controller, self._burst_rate_hz, self._burst_duration_s):
                break


def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> MicroburstTimeProfile:
    """
    Factory for the microburst time profile.
    """
    _ = settings

    idle_rate_hz = base.parse_float(args, "idle_rate_hz", default=0.1)
    idle_duration_s = base.parse_float(args, "idle_duration_s", default=10.0)
    burst_rate_hz = base.parse_float(args, "burst_rate_hz", default=20.0)
    burst_duration_s = base.parse_float(args, "burst_duration_s", default=1.0)
    cycles = base.parse_int(args, "cycles", default=10)
    seed_str = args.get("seed")

    if idle_duration_s is None or burst_rate_hz is None or burst_duration_s is None or cycles is None:
        raise ValueError("microburst profile requires idle_duration_s, burst_rate_hz, burst_duration_s and cycles.")

    rng = base.make_rng(global_seed, seed_str)
    return MicroburstTimeProfile(
        idle_rate_hz=float(idle_rate_hz or 0.0),
        idle_duration_s=float(idle_duration_s),
        burst_rate_hz=float(burst_rate_hz),
        burst_duration_s=float(burst_duration_s),
        cycles=int(cycles),
        rng=rng,
    )
