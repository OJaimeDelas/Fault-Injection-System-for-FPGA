# =============================================================================
# FATORI-V • FI Time Profiles Base Utilities
# File: base.py
# -----------------------------------------------------------------------------
# Shared helpers for time profiles.
#
# Time profiles implement:
#     run(controller) -> None
#
# where `controller` is an InjectionController instance with methods:
#     next_target()  -> TargetSpec | None
#     inject_target(target: TargetSpec) -> bool
#     sleep(seconds: float) -> None
#     should_stop() -> bool
#
# This module provides small utilities for argument parsing and for sampling
# inter-arrival times for stochastic profiles.
#=============================================================================

from __future__ import annotations

import math
import random
import time
from typing import Dict, Optional


def parse_float(args: Dict[str, str], key: str, default: Optional[float]) -> Optional[float]:
    """
    Convert a dictionary entry to float, handling missing keys and blanks.

    If the key is missing or the value is an empty string, the default is
    returned. Numeric values may be given in integer or float notation.
    """
    if key not in args:
        return default
    raw = args[key].strip()
    if not raw:
        return default
    return float(raw)


def parse_int(args: Dict[str, str], key: str, default: Optional[int]) -> Optional[int]:
    """
    Convert a dictionary entry to int, using Python's base-detection rules.

    If the key is missing or the value is an empty string, the default is
    returned. Values may use prefixes such as '0x' for hexadecimal.
    """
    if key not in args:
        return default
    raw = args[key].strip()
    if not raw:
        return default
    return int(raw, 0)


def make_rng(global_seed: Optional[int], local_seed_str: Optional[str]) -> random.Random:
    """
    Build a random.Random instance using either a local seed or the global
    engine seed.

    local_seed_str:
        String representation of the local seed (from args), or None.
    global_seed:
        Integer seed from the engine Config, or None.
    """
    if local_seed_str is not None and local_seed_str != "":
        seed = int(local_seed_str, 0)
    else:
        seed = global_seed
    return random.Random(seed)


def now_monotonic() -> float:
    """
    Convenience wrapper for time.monotonic(), used by time profiles to measure
    elapsed time and schedule deadlines.
    """
    return time.monotonic()


def sample_exponential(rng: random.Random, rate_hz: float) -> float:
    """
    Draw a non-negative exponentially distributed inter-arrival time with a
    given rate (events per second).

    rate_hz must be strictly positive. The returned value is in seconds.
    """
    if rate_hz <= 0.0:
        raise ValueError("Exponential sampling requires rate_hz > 0.")
    # Inverse CDF sampling: -ln(U) / λ
    u = rng.random()
    while u <= 0.0:
        u = rng.random()
    return -math.log(u) / rate_hz
