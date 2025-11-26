# =============================================================================
# FATORI-V • FI Engine
# File: seed_manager.py
# -----------------------------------------------------------------------------
# Seed derivation and management for reproducible campaigns.
#=============================================================================

import random
from typing import Optional, Callable


def derive_area_seed(global_seed: int) -> int:
    """
    Derive area profile seed from global seed.
    
    Uses hash-based derivation to ensure different seeds for each
    profile type while remaining deterministic.
    
    Args:
        global_seed: Master seed for campaign
    
    Returns:
        Derived seed for area profile (32-bit integer)
    """
    return hash(("area", global_seed)) % (2**32)


def derive_time_seed(global_seed: int) -> int:
    """
    Derive time profile seed from global seed.
    
    Uses hash-based derivation to ensure different seeds for each
    profile type while remaining deterministic.
    
    Args:
        global_seed: Master seed for campaign
    
    Returns:
        Derived seed for time profile (32-bit integer)
    """
    return hash(("time", global_seed)) % (2**32)


def get_effective_seed(
    explicit: Optional[int],
    global_seed: Optional[int],
    derive_fn: Callable[[int], int]
) -> Optional[int]:
    """
    Get effective seed using fallback chain.
    
    Seed resolution priority:
    1. Explicit seed (e.g., --area-seed 12345)
    2. Derived from global seed (via derive_fn)
    3. None (profile will use random seed)
    
    Args:
        explicit: Explicitly specified seed (or None)
        global_seed: Global seed to derive from (or None)
        derive_fn: Function to derive seed from global seed
    
    Returns:
        Effective seed to use, or None if no seed specified
    
    Example:
        >>> # Case 1: Explicit seed takes priority
        >>> get_effective_seed(explicit=999, global_seed=100, derive_fn=derive_area_seed)
        999
        
        >>> # Case 2: Derive from global seed
        >>> get_effective_seed(explicit=None, global_seed=100, derive_fn=derive_area_seed)
        <derived value>
        
        >>> # Case 3: No seed (profile uses random)
        >>> get_effective_seed(explicit=None, global_seed=None, derive_fn=derive_area_seed)
        None
    """
    # Priority 1: Explicit seed overrides everything
    if explicit is not None:
        return explicit
    
    # Priority 2: Derive from global seed
    if global_seed is not None:
        return derive_fn(global_seed)
    
    # Priority 3: No seed (let profile use random)
    return None


def format_seed_source(
    explicit: Optional[int],
    global_seed: Optional[int],
    effective: Optional[int]
) -> str:
    """
    Format human-readable seed source for logging.
    
    Produces strings like:
    - "12345 (explicit)"
    - "67890 (derived from global)"
    - "random"
    
    Args:
        explicit: Explicit seed value or None
        global_seed: Global seed value or None
        effective: The actual seed being used (or None for random)
    
    Returns:
        Formatted string describing seed source
    """
    if effective is None:
        return "random"
    elif explicit is not None:
        return f"{effective} (explicit)"
    elif global_seed is not None:
        return f"{effective} (derived from global)"
    else:
        return f"{effective}"