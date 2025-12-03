# =============================================================================
# FATORI-V • FI Engine Pool Builder
# File: pool_builder.py
# -----------------------------------------------------------------------------
# Helper to build TargetPool from area profile with logging and export.
#=============================================================================

import logging

from fi.targets.pool import TargetPool
from fi.targets.pool_writer import save_pool_with_copies
from fi.core.logging.events import log_pool_built

logger = logging.getLogger(__name__)


def build_campaign_pool(
    area_profile,
    system_dict,
    board_name: str,
    ebd_path: str,
    cfg
) -> TargetPool:
    """
    Build TargetPool using area profile and optionally export to YAML.
    
    This helper orchestrates the pool building process:
    1. Call area_profile.build_pool() to generate targets
    2. Get pool statistics
    3. Log pool building results
    4. Optionally export pool to YAML file for reproducibility
    5. Return the built pool
    
    Args:
        area_profile: Loaded area profile instance (has build_pool method)
        system_dict: SystemDict with board dictionaries
        board_name: Resolved board name
        ebd_path: Path to EBD file
        cfg: Config instance with TargetPool export settings
    
    Returns:
        TargetPool ready for injection
    
    Raises:
        Any exceptions from area_profile.build_pool()
    """
    # Build pool using area profile, passing config for tpool settings
    pool = area_profile.build_pool(
        system_dict=system_dict,
        board_name=board_name,
        ebd_path=ebd_path,
        cfg=cfg
    )
    
    # Get pool statistics for logging
    stats = pool.get_stats()
    
    # Log pool building results
    log_pool_built(stats, profile_name=area_profile.name)
    
    # Automatically save pool to YAML if enabled
    if cfg.tpool_auto_save:
        try:
            paths = save_pool_with_copies(
                pool=pool,
                custom_name=cfg.tpool_output_name,
                profile_name=area_profile.name,
                board_name=board_name,
                output_dir=cfg.tpool_output_dir,
                additional_path=cfg.tpool_additional_path
            )
            
            logger.info(f"Saved pool to {paths['primary']}")
            
            # Log additional copy if created
            if paths['copy']:
                logger.info(f"Copied pool to {paths['copy']}")
                
        except Exception as e:
            # Log error but don't fail the campaign
            # Pool is still usable even if export failed
            logger.error(f"Failed to save pool YAML: {e}")
    
    return pool