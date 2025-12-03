# =============================================================================
# FATORI-V • FI Profiles Area
# File: device.py
# -----------------------------------------------------------------------------
# Device-wide injection profile (all configuration bits + all registers).
#=============================================================================

from typing import Dict, Any

from fi.profiles.area.base import AreaProfileBase
from fi.profiles.area.common.ratio_selector import RatioSelector
from fi.targets.pool import TargetPool
from fi.targets.types import TargetSpec, TargetKind
from fi.backend.acme.decoder import expand_device_to_config_bits


# -----------------------------------------------------------------------------
# Plugin metadata
# -----------------------------------------------------------------------------

PROFILE_KIND = "area"
PROFILE_NAME = "device"


def describe() -> str:
    """
    Return human-readable description of this profile.
    
    Returns:
        Description string for help/documentation
    """
    return "Inject into entire device (all configuration bits + all registers)"


def default_args() -> Dict[str, Any]:
    """
    Return default argument values for this profile.
    
    Returns:
        Dict of default arguments
    """
    return {
        "mode": "sequential",    # sequential, random
        "ratio": 0.5,           # Proportion of REG targets (0.0-1.0)
        "repeat": True,         # Allow target repetition
        "tpool_size": 200,      # Pool size when repeat=True
        "sample_size": None,    # Optional: limit number of CONFIG addresses from ACME
    }


def make_profile(args: Dict[str, Any], *, global_seed, settings) -> AreaProfileBase:
    """
    Factory function to create profile instance.
    
    Args:
        args: Profile arguments from CLI
        global_seed: Global RNG seed for reproducibility
        settings: FI settings object
    
    Returns:
        DeviceProfile instance
    """
    return DeviceProfile(
        name=PROFILE_NAME,
        args=args,
        global_seed=global_seed
    )


# -----------------------------------------------------------------------------
# Profile implementation
# -----------------------------------------------------------------------------

class DeviceProfile(AreaProfileBase):
    """
    Device-wide fault injection profile with ratio and repeat support.
    
    This profile targets the entire FPGA device by:
    1. Expanding full device bounds to ALL configuration bit addresses via ACME
    2. Collecting ALL registers from ALL targets in the system dict
    3. Intermixing CONFIG and REG targets based on ratio parameter
    4. Supporting repeat mode for infinite pools
    
    Arguments:
        mode: Ordering mode (sequential, random) - can also use "order"
        ratio: Proportion of REG targets (0.0=all CONFIG, 1.0=all REG, 0.5=equal)
        repeat: Allow target repetition (True=infinite pool, False=exhaust targets)
        tpool_size: Target pool size (only used when repeat=True)
        sample_size: Optional limit on number of CONFIG addresses from ACME
    """
    
    def build_pool(self, system_dict, board_name: str, ebd_path: str, cfg) -> TargetPool:
        """
        Build TargetPool for entire device with ratio and repeat support.
        
        High-level algorithm:
        1. Get device bounds from SystemDict
        2. Expand full device to ALL config bits via ACME
        3. Build ALL CONFIG targets
        4. Build ALL register targets
        5. Order each group based on mode (sequential or shuffle)
        6. Intermix CONFIG and REG targets using RatioSelector
        7. Add to pool in final order
        
        Args:
            system_dict: SystemDict with board dictionaries
            board_name: Resolved board name
            ebd_path: Path to EBD file
            cfg: Config instance with tpool settings
        
        Returns:
            TargetPool with device-wide targets in specified order
        """
        # Get board dictionary
        if board_name not in system_dict.boards:
            raise ValueError(f"Board '{board_name}' not in SystemDict")
        
        board_dict = system_dict.boards[board_name]
        
        # Get device bounds as coordinate dict
        device_coords = {
            'x_lo': board_dict.device.min_x,
            'y_lo': board_dict.device.min_y,
            'x_hi': board_dict.device.max_x,
            'y_hi': board_dict.device.max_y
        }
        
        # Expand entire device to configuration bit addresses via ACME
        addresses = expand_device_to_config_bits(
            device_coords=device_coords,
            board_name=board_name,
            ebd_path=ebd_path,
            use_cache=cfg.acme_cache_enabled,
            cache_dir=cfg.acme_cache_dir
        )
        
        # Optional sampling to limit CONFIG addresses
        sample_size = self.args.get("sample_size")
        if sample_size is not None:
            sample_size = int(sample_size)
            if len(addresses) > sample_size:
                addresses = self.rng.sample(addresses, sample_size)
        
        # Build list of ALL CONFIG targets
        all_config_targets = []
        for addr in addresses:
            all_config_targets.append(TargetSpec(
                kind=TargetKind.CONFIG,
                module_name="device",
                config_address=addr,
                pblock_name=None,
                source="profile:device"
            ))
        
        # Build list of ALL register targets from complete register index
        # Device profile injects into EVERYTHING, so use all registers in system_dict
        all_reg_targets = []
        for reg_id, reg_info in board_dict.registers.items():
            all_reg_targets.append(TargetSpec(
                kind=TargetKind.REG,
                module_name=reg_info.module,  # Use module from register info
                reg_id=reg_id,
                reg_name=reg_info.name,
                source="profile:device"
            ))
        
        # Apply ordering mode to each group separately
        # Accept both "order" and "mode" as parameter names (order takes priority)
        mode = self.args.get("order") or self.args.get("mode", "sequential")

        if mode == "random":
            # Shuffle each group independently using seeded RNG
            self.rng.shuffle(all_config_targets)
            self.rng.shuffle(all_reg_targets)
        # sequential mode: keep in SystemDict order (no shuffle)
        
        # Parse ratio and repeat parameters
        ratio = float(self.args.get("ratio", 0.5))
        repeat = self.args.get("repeat", True)
        if isinstance(repeat, str):
            repeat = repeat.lower() in ("true", "1", "yes", "on")
        
        from fi import fi_settings
        
        # Parse tpool_size from args (always parse it, regardless of repeat mode)
        tpool_size_arg = self.args.get("tpool_size")
        if tpool_size_arg is not None:
            tpool_size = int(tpool_size_arg)
        elif repeat:
            # Use default from settings only in repeat mode
            tpool_size = fi_settings.TPOOL_DEFAULT_SIZE
        else:
            tpool_size = None
        
        # Use RatioSelector to intermix CONFIG and REG respecting ratio
        selector = RatioSelector(
            ratio=ratio,
            repeat=repeat,
            rng=self.rng,
            target_count=tpool_size,
            cfg=cfg,
            ratio_strict=cfg.ratio_strict if cfg else False
        )
        
        # Build intermixed pool
        if mode == "random":
            intermixed_targets = selector.build_random_intermixed_pool(
                config_targets=all_config_targets,
                reg_targets=all_reg_targets
            )
        else:
            intermixed_targets = selector.build_sequential_intermixed_pool(
                config_targets=all_config_targets,
                reg_targets=all_reg_targets
            )
        
        # Build final pool
        pool = TargetPool()
        for target in intermixed_targets:
            pool.add(target)
        
        return pool