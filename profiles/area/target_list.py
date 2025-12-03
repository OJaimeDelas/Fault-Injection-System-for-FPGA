# =============================================================================
# FATORI-V • FI Profiles Area
# File: target_list.py
# -----------------------------------------------------------------------------
# Load explicit target list from YAML pool file.
#=============================================================================

from typing import Dict, Any

from fi.profiles.area.base import AreaProfileBase
from fi.targets.pool import TargetPool
from fi.targets.pool_loader import load_pool_from_file
from fi import fi_settings


# -----------------------------------------------------------------------------
# Plugin metadata
# -----------------------------------------------------------------------------

PROFILE_KIND = "area"
PROFILE_NAME = "target_list"


def describe() -> str:
    """
    Return human-readable description of this profile.
    
    Returns:
        Description string for help/documentation
    """
    return "Load explicit target list from YAML file"


def default_args() -> Dict[str, Any]:
    """
    Return default argument values for this profile.
    
    Returns:
        Dict of default arguments
    """
    return {
        "pool_file": fi_settings.INJECTION_POOL_DEFAULT_PATH, 
    }


def make_profile(args: Dict[str, Any], *, global_seed, settings) -> AreaProfileBase:
    """
    Factory function to create profile instance.
    
    Args:
        args: Argument dict (CLI args merged with defaults)
        global_seed: Master seed for reproducibility (or None)
        settings: fi_settings module
    
    Returns:
        TargetListAreaProfile instance
    
    Raises:
        ValueError: If pool_file argument not provided
    """
    # Validate that pool_file is provided
    if not args.get("pool_file"):
        raise ValueError(
            "target_list profile requires 'pool_file' argument. "
            "Usage: --area target_list --area-args 'pool_file=/path/to/pool.yaml'"
        )
    
    return TargetListAreaProfile(
        name=PROFILE_NAME,
        args=args,
        global_seed=global_seed
    )


# -----------------------------------------------------------------------------
# Profile implementation
# -----------------------------------------------------------------------------

class TargetListAreaProfile(AreaProfileBase):
    """
    Area profile that loads targets from explicit YAML file.
    
    This is the simplest area profile - it just loads a pre-built target
    pool from a YAML file and returns it. No expansion, no selection logic,
    just a pass-through from file to pool.
    
    Use Cases:
        - Reproducible campaigns with exact target lists
        - Custom target orderings from external tools
        - Testing specific target combinations
        - Pre-computed target sets
    
    Pool File Format:
```yaml
        targets:
          - kind: CONFIG
            module_name: "alu"
            config_address: "00001234"
            pblock_name: "alu_pb"
          
          - kind: REG
            module_name: "decoder"
            reg_id: 5
            reg_name: "dec_rec_q"
```
    
    Arguments:
        pool_file (required): Path to YAML pool file
    
    Example Usage:
```bash
        python -m fi.fault_injection \
            --area target_list \
            --area-args "pool_file=/path/to/targets.yaml"
```
    """
    
    def build_pool(self, system_dict, board_name, ebd_path, cfg) -> TargetPool:
        """
        Load pool from YAML file.
        
        This method simply delegates to pool_loader.load_pool_from_file().
        The system_dict, board_name, ebd_path, and cfg parameters are not used
        since the pool is already fully specified in the file.
        
        Args:
            system_dict: SystemDict (unused, pool is pre-built)
            board_name: Board name (unused, pool is pre-built)
            ebd_path: EBD file path (unused, pool is pre-built)
            cfg: Config instance (unused, pool is pre-built)
        
        Returns:
            TargetPool loaded from file
        
        Raises:
            ValueError: If pool file cannot be loaded
        """
        pool_file = self.args["pool_file"]
        from fi.core.logging.events import log_target_list_loading
        log_target_list_loading(pool_file)
        
        # Load pool from file using pool_loader
        pool = load_pool_from_file(pool_file)
        
        # Check if loading failed
        if pool is None:
            raise ValueError(
                f"Failed to load pool from {pool_file}. "
                "Check that the file exists and has valid YAML format."
            )
        
        from fi.core.logging.events import log_target_list_loaded
        log_target_list_loaded(len(pool))
        
        # Get pool statistics for logging
        stats = pool.get_stats()
        from fi.core.logging.events import log_target_list_stats
        log_target_list_stats(stats)
        
        return pool