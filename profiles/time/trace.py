# =============================================================================
# FATORI-V • FI Time Profile — Trace-Based Schedule
# File: trace.py
# -----------------------------------------------------------------------------
# Time profile that replays a schedule of injection times from a trace file.
#
# The trace is a text file with one timestamp per line, representing the
# absolute time offset (in seconds) from the start of the campaign.
#
# Parameters (from args dict):
#   path       : path to the trace file (required)
#   scale      : optional multiplicative factor applied to all timestamps
#                (float, default 1.0)
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
        "path": "",
        "scale": 1.0,
    }


class TraceTimeProfile:
    """
    Replays injection times taken from a trace file. Each line in the file
    is a non-negative timestamp (seconds from campaign start).
    """

    def __init__(self, path: str, scale: float) -> None:
        self._path = pathlib.Path(path)
        self._scale = scale
        self._schedule: List[float] = []

        self._load_schedule()

    def _load_schedule(self) -> None:
        """
        Load and scale timestamps from the trace file.
        """
        if not self._path.is_file():
            raise FileNotFoundError(f"Trace file not found: {self._path}")

        schedule: List[float] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                ts = float(line)
                if ts < 0.0:
                    continue
                schedule.append(ts * self._scale)

        schedule.sort()
        self._schedule = schedule

    def run(self, controller) -> None:
        """
        Drive the injection controller according to the loaded schedule.
        """
        if not self._schedule:
            return

        start_t = base.now_monotonic()

        for t_offset in self._schedule:
            if controller.should_stop():
                break

            target = controller.next_target()
            if target is None:
                break

            # Compute absolute deadline and sleep until then.
            deadline = start_t + t_offset
            now = base.now_monotonic()
            delay = deadline - now
            if delay > 0.0:
                controller.sleep(delay)

            controller.inject_target(target)


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

    path = args.get("path", "").strip()
    if not path:
        raise ValueError("trace profile requires a non-empty 'path' argument.")

    scale = base.parse_float(args, "scale", default=1.0)
    if scale is None or scale <= 0.0:
        raise ValueError("trace profile requires scale > 0.")

    return TraceTimeProfile(path=path, scale=float(scale))
