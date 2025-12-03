# =============================================================================
# FATORI-V • FI Time Profile — Microburst
# File: microburst.py
# -----------------------------------------------------------------------------
# Time profile that alternates between idle periods and short high-rate burst
# periods, useful for stressing systems with clustered injections.
#
# Parameters (from args dict):
#   burst_rate_hz    : Injection rate during burst periods (float > 0, required)
#   idle_rate_hz     : Injection rate during idle periods (float >= 0, default 0)
#   burst_duration_s : Duration of each burst period in seconds (float > 0, required)
#   idle_duration_s  : Duration of each idle period in seconds (float > 0, required)
#   bursts           : Number of bursts to execute (int > 0, optional)
#   duration_s       : Overall time limit in seconds (float, optional)
#   seed             : Optional local seed; if omitted, global_seed is used
#
# If both 'bursts' and 'duration_s' are set, whichever occurs first ends the profile.
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
        "burst_rate_hz": 5.0,
        "idle_rate_hz": 0.0,
        "burst_duration_s": 1.0,
        "idle_duration_s": 2.0,
        "bursts": None,
        "duration_s": None,
        "seed": None,
    }


class MicroburstTimeProfile:
    """
    Alternates between idle and burst periods, each modelled as a Poisson
    process with its own rate and duration.
    
    The profile ends when either:
    - The requested number of bursts completes (if bursts is set)
    - The duration limit is reached (if duration_s is set)
    - The target pool is exhausted
    Whichever comes first.
    """

    def __init__(
        self,
        burst_rate_hz: float,
        idle_rate_hz: float,
        burst_duration_s: float,
        idle_duration_s: float,
        bursts: Optional[int],
        duration_s: Optional[float],
        rng,
    ) -> None:
        if idle_duration_s <= 0.0 or burst_duration_s <= 0.0:
            raise ValueError("microburst profile requires positive durations.")
        if burst_rate_hz <= 0.0:
            raise ValueError("microburst profile requires burst_rate_hz > 0.")
        if bursts is not None and bursts <= 0:
            raise ValueError("microburst profile requires bursts > 0 if specified.")
        if duration_s is not None and duration_s <= 0.0:
            raise ValueError("microburst profile requires duration_s > 0 if specified.")

        self._burst_rate_hz = burst_rate_hz
        self._idle_rate_hz = max(idle_rate_hz, 0.0)
        self._burst_duration_s = burst_duration_s
        self._idle_duration_s = idle_duration_s
        self._bursts = bursts
        self._duration_s = duration_s
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
        Execute idle+burst cycles until one of the end conditions is met:
        - Number of bursts reached (if bursts is set)
        - Duration limit reached (if duration_s is set)
        - Controller requests stop
        - Target pool exhausted
        """
        campaign_start = base.now_monotonic()
        burst_count = 0
        
        while True:
            # Check if requested number of bursts completed
            if self._bursts is not None and burst_count >= self._bursts:
                controller.set_termination_reason("Requested number of bursts completed")
                break
            
            # Check if duration limit reached
            if self._duration_s is not None:
                elapsed = base.now_monotonic() - campaign_start
                if elapsed >= self._duration_s:
                    controller.set_termination_reason("Duration limit reached")
                    break
            
            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break
                
            # Idle interval
            if not self._run_interval(controller, self._idle_rate_hz, self._idle_duration_s):
                # _run_interval returns False on stop or pool exhaustion
                if controller.should_stop():
                    controller.set_termination_reason("Stop requested")
                else:
                    controller.set_termination_reason("Target pool exhausted")
                break
                
            # Check duration limit again after idle
            if self._duration_s is not None:
                elapsed = base.now_monotonic() - campaign_start
                if elapsed >= self._duration_s:
                    controller.set_termination_reason("Duration limit reached")
                    break
                    
            if controller.should_stop():
                controller.set_termination_reason("Stop requested")
                break
                
            # Burst interval
            if not self._run_interval(controller, self._burst_rate_hz, self._burst_duration_s):
                # _run_interval returns False on stop or pool exhaustion
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
    """
    Factory for the microburst time profile.
    """
    _ = settings

    burst_rate_hz = base.parse_float(args, "burst_rate_hz", default=None)
    idle_rate_hz = base.parse_float(args, "idle_rate_hz", default=0.0)
    burst_duration_s = base.parse_float(args, "burst_duration_s", default=None)
    idle_duration_s = base.parse_float(args, "idle_duration_s", default=None)
    bursts = base.parse_int(args, "bursts", default=None)
    duration_s = base.parse_float(args, "duration_s", default=None)
    seed_str = args.get("seed")

    if burst_rate_hz is None or burst_duration_s is None or idle_duration_s is None:
        raise ValueError("microburst profile requires burst_rate_hz, burst_duration_s and idle_duration_s.")

    rng = base.make_rng(global_seed, seed_str)
    return MicroburstTimeProfile(
        burst_rate_hz=float(burst_rate_hz),
        idle_rate_hz=float(idle_rate_hz or 0.0),
        burst_duration_s=float(burst_duration_s),
        idle_duration_s=float(idle_duration_s),
        bursts=bursts,
        duration_s=duration_s,
        rng=rng,
    )
