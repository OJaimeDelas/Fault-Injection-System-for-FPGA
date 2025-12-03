# =============================================================================
# FATORI-V • FI Time Profile — Trace-Based Schedule
# File: trace.py
# -----------------------------------------------------------------------------
# Time profile that replays a schedule of injection times from a trace file.
#
# The trace is a text file with one value per line:
#   - mode='absolute': absolute time offsets (seconds from campaign start)
#   - mode='relative': inter-arrival gaps (seconds between injections)
#
# Parameters (from args dict):
#   file (or path)  : Path to the trace file (required)
#   mode            : "absolute" or "relative" (default "absolute")
#   repeat          : Number of times to replay the schedule (int >= 1, default 1)
#   duration_s      : Optional time limit; stops even if schedule has entries left
#=============================================================================

from __future__ import annotations

import pathlib
from typing import Any, Dict, List, Optional

from fi.profiles.time import base


PROFILE_KIND = "time"
PROFILE_NAME = "trace"


def describe() -> str:
    """
    Human-readable one-line description of this time profile.
    """
    return "Replay injections at times defined by a trace file (seconds offset)."


def default_args() -> Dict[str, Any]:
    """
    Default argument values for documentation and tooling.
    """
    return {
        "file": "profiles/time/schedules/example_trace.txt",
        "path": "",  # Alias for 'file'
        "mode": "absolute",
        "repeat": 1,
        "duration_s": None,
    }


class TraceTimeProfile:
    """
    Replays injection times taken from a trace file.
    
    Supports two modes:
    - 'absolute': Each line is an absolute timestamp (seconds from campaign start)
    - 'relative': Each line is an inter-arrival gap (seconds between injections)
    """

    def __init__(
        self, 
        path: str, 
        mode: str, 
        repeat: int,
        duration_s: Optional[float]
    ) -> None:
        self._path = pathlib.Path(path)
        self._mode = mode.lower()
        self._repeat = repeat
        self._duration_s = duration_s
        self._schedule: List[float] = []

        if self._mode not in ("absolute", "relative"):
            raise ValueError(f"trace mode must be 'absolute' or 'relative', got: {mode}")
        if self._repeat < 1:
            raise ValueError("trace repeat must be >= 1")

        self._load_schedule()

    def _load_schedule(self) -> None:
        """
        Load timestamps or intervals from the trace file.
        
        Supports two line formats:
        - Single float: "0.500"
        - Timestamp with event: "0.500 inject" (extracts timestamp only)
        """
        if not self._path.is_file():
            raise FileNotFoundError(f"Trace file not found: {self._path}")

        values: List[float] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line_num, raw_line in enumerate(fh, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # Handle "timestamp event_type" format (e.g., "0.500 inject")
                # or simple "timestamp" format (e.g., "0.500")
                parts = line.split()
                if not parts:
                    continue
                
                try:
                    val = float(parts[0])  # Take first token as timestamp
                except ValueError as e:
                    raise ValueError(
                        f"Invalid value in trace file {self._path} "
                        f"at line {line_num}: '{line}'. "
                        f"Expected format: '<timestamp>' or '<timestamp> <event_type>'"
                    ) from e
                
                if val < 0.0:
                    continue
                values.append(val)

        if not values:
            raise ValueError(f"No valid values found in trace file: {self._path}")

        if self._mode == "absolute":
            # Sort to ensure chronological order
            values.sort()
            self._schedule = values
        else:  # relative (intervals)
            # Convert intervals to absolute timestamps
            cumulative = 0.0
            timestamps = []
            for interval in values:
                cumulative += interval
                timestamps.append(cumulative)
            self._schedule = timestamps
   
    def run(self, controller) -> None:
        """
        Drive the injection controller according to the loaded schedule.
        Repeats the schedule the specified number of times.
        """
        if not self._schedule:
            controller.set_termination_reason("Empty schedule")
            return

        campaign_start = base.now_monotonic()
        completed_all_cycles = True

        for cycle in range(self._repeat):
            cycle_start = base.now_monotonic()
            
            for t_offset in self._schedule:
                if controller.should_stop():
                    controller.set_termination_reason("Stop requested")
                    return
                
                # Check duration limit
                if self._duration_s is not None:
                    elapsed = base.now_monotonic() - campaign_start
                    if elapsed >= self._duration_s:
                        controller.set_termination_reason("Duration limit reached")
                        return

                target = controller.next_target()
                if target is None:
                    controller.set_termination_reason("Target pool exhausted")
                    return

                # Compute absolute deadline and sleep until then
                deadline = cycle_start + t_offset
                now = base.now_monotonic()
                delay = deadline - now
                if delay > 0.0:
                    controller.sleep(delay)

                controller.inject_target(target)
        
        # If we get here, all cycles and schedule entries completed
        if self._repeat > 1:
            controller.set_termination_reason(f"Schedule completed ({self._repeat} cycles)")
        else:
            controller.set_termination_reason("Schedule completed")

def make_profile(
    args: Dict[str, str],
    *,
    global_seed: Optional[int],
    settings: Any,
) -> TraceTimeProfile:
    """
    Factory for the trace-based time profile.
    """
    _ = global_seed, settings

    # Accept either 'file' or 'path' as the file path
    path = args.get("file", "").strip() or args.get("path", "").strip()
    if not path:
        raise ValueError(
            "trace profile requires 'file' argument. "
            "Example: --time-args \"file=/path/to/schedule.txt,mode=absolute\""
        )

    mode = args.get("mode", "absolute").strip().lower()
    if not mode:
        mode = "absolute"  # Default if empty string provided
    
    if mode not in ("absolute", "relative"):
        raise ValueError(
            f"trace profile mode must be 'absolute' or 'relative', got: '{mode}'. "
            "Use mode=absolute for timestamps from campaign start, "
            "or mode=relative for inter-arrival intervals."
        )

    repeat = base.parse_int(args, "repeat", default=1)
    duration_s = base.parse_float(args, "duration_s", default=None)

    if repeat is None or repeat < 1:
        raise ValueError("trace profile requires repeat >= 1.")

    return TraceTimeProfile(
        path=path, 
        mode=mode, 
        repeat=int(repeat),
        duration_s=duration_s
    )