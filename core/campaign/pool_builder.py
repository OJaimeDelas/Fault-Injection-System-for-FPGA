# =============================================================================
# FATORI-V • FI Engine
# File: pool_builder.py
# -----------------------------------------------------------------------------
# Helper to build TargetPool from area profile with logging.
#=============================================================================

from fi.targets.pool import TargetPool
from fi.core.logging.events import log_pool_built


def build_campaign_pool(
    area_profile,
    system_dict,
    board_name: str,
    ebd_path: str
) -> TargetPool:
    """
    Build TargetPool using area profile.
    
    This helper orchestrates the pool building process:
    1. Call area_profile.build_pool() to generate targets
    2. Get pool statistics
    3. Log pool building results
    4. Return the built pool
    
    Args:
        area_profile: Loaded area profile instance (has build_pool method)
        system_dict: SystemDict with board dictionaries
        board_name: Resolved board name
        ebd_path: Path to EBD file
    
    Returns:
        TargetPool ready for injection
    
    Raises:
        Any exceptions from area_profile.build_pool()
    """
    # Build pool using area profile
    pool = area_profile.build_pool(
        system_dict=system_dict,
        board_name=board_name,
        ebd_path=ebd_path
    )
    
    # Get pool statistics for logging
    stats = pool.get_stats()
    
    # Log pool building results
    log_pool_built(stats, profile_name=area_profile.name)
    
    return pool