# =============================================================================
# FATORI-V • FI Engine
# File: seed_manager.py
# -----------------------------------------------------------------------------
# Seed derivation and management for reproducible campaigns.
#=============================================================================

import random
from typing import Optional, Callable
import time

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


def generate_global_seed() -> int:
    """
    Generate a random global seed for campaign reproducibility.
    
    Uses time and random state to create a unique seed value.
    The seed is a 32-bit integer suitable for Python's random module.
    
    Returns:
        Generated seed (32-bit integer)
    """
    # Combine time-based and random components for uniqueness
    # Time component ensures different seeds across campaigns
    # Random component ensures different seeds within same second
    time_component = int(time.time() * 1000) % (2**31)
    random_component = random.randint(0, 2**31 - 1)
    
    # XOR the components and keep within 32-bit range
    seed = (time_component ^ random_component) % (2**32)
    
    return seed

def get_effective_seed(
    explicit: Optional[int],
    global_seed: Optional[int],
    derive_fn: Optional[Callable[[int], int]] = None
) -> Optional[int]:
    """
    Get effective seed using fallback chain.
    
    Seed resolution priority:
    1. Explicit seed (e.g., --area-seed 12345)
    2. Global seed used directly (NOT derived)
    3. None (profile will use random seed)
    
    The global seed is used as-is for all profiles that don't have
    explicit seeds. This ensures reproducibility while keeping the
    same seed across area and time profiles.
    
    Args:
        explicit: Explicitly specified seed (or None)
        global_seed: Global seed to use directly (or None)
        derive_fn: Deprecated, kept for API compatibility but unused
    
    Returns:
        Effective seed to use, or None if no seed specified
    
    Example:
        >>> # Case 1: Explicit seed takes priority
        >>> get_effective_seed(explicit=999, global_seed=100)
        999
        
        >>> # Case 2: Use global seed directly
        >>> get_effective_seed(explicit=None, global_seed=100)
        100
        
        >>> # Case 3: No seed (profile uses random)
        >>> get_effective_seed(explicit=None, global_seed=None)
        None
    """
    # Priority 1: Explicit seed overrides everything
    if explicit is not None:
        return explicit
    
    # Priority 2: Use global seed directly (NOT derived)
    if global_seed is not None:
        return global_seed
    
    # Priority 3: No seed (let profile use random)
    return None

def format_seed_source(
    explicit: Optional[int],
    global_seed: Optional[int],
    effective: Optional[int],
    is_generated: bool = False
) -> str:
    """
    Format human-readable seed source for logging.
    
    Produces strings like:
    - "12345 (explicit)"
    - "12345 (from global)" when using global seed directly
    - "54321 (generated)"
    - "random"
    
    Args:
        explicit: Explicit seed value or None
        global_seed: Global seed value or None
        effective: The actual seed being used (or None for random)
        is_generated: Whether the seed was auto-generated (for global seed only)
    
    Returns:
        Formatted string describing seed source
    """
    if effective is None:
        return "random"
    elif explicit is not None:
        return f"{effective} (explicit)"
    elif is_generated:
        return f"{effective} (generated)"
    elif global_seed is not None and effective == global_seed:
        # Using global seed directly (not derived)
        return f"{effective} (from global)"
    elif global_seed is not None:
        # Different from global seed (should not happen with new logic)
        return f"{effective} (derived from global)"
    else:
        return f"{effective}"