# =============================================================================
# FATORI-V • FI Profiles Area
# File: device.py
# -----------------------------------------------------------------------------
# Device-wide injection profile (all configuration bits + all registers).
#=============================================================================

from typing import Dict, Any

from fi.profiles.area.base import AreaProfileBase
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
        "mode": "sequential",  # sequential, shuffled, random
        "seed": None,          # Override seed
        "sample_size": None,   # Optional: limit number of addresses
    }


def make_profile(args: Dict[str, Any], *, global_seed, settings) -> AreaProfileBase:
    """
    Factory function to create profile instance.
    
    Args:
        args: Argument dict (CLI args merged with defaults)
        global_seed: Master seed for reproducibility (or None)
        settings: fi_settings module
    
    Returns:
        DeviceAreaProfile instance
    """
    merged = default_args()
    merged.update(args)
    return DeviceAreaProfile(
        name=PROFILE_NAME,
        args=merged,
        global_seed=global_seed
    )


# -----------------------------------------------------------------------------
# Profile implementation
# -----------------------------------------------------------------------------

class DeviceAreaProfile(AreaProfileBase):
    """
    Area profile for device-wide injection.
    
    This profile injects across the entire FPGA device by:
    1. Getting full_device_region from SystemDict
    2. Expanding it to all configuration bit addresses via ACME
    3. Adding all registers from all modules
    4. Optionally sampling and reordering
    
    This provides comprehensive fault injection coverage across both
    configuration memory and register state.
    """
    
    def build_pool(self, system_dict, board_name: str, ebd_path: str):
        """
        Build TargetPool with device-wide CONFIG targets + all registers.
        
        Process:
        1. Get full_device_region from board dictionary
        2. Expand to all config bit addresses via ACME
        3. Optionally sample if sample_size specified
        4. Apply ordering mode (sequential/shuffled/random)
        5. Build TargetPool with CONFIG targets
        6. Add ALL registers from ALL modules
        
        Args:
            system_dict: SystemDict with board dictionaries
            board_name: Resolved board name
            ebd_path: Path to EBD file
        
        Returns:
            TargetPool with device-wide CONFIG targets + all registers
        """
        # Get board dictionary
        if board_name not in system_dict.boards:
            raise ValueError(f"Board '{board_name}' not in SystemDict")
        
        board_dict = system_dict.boards[board_name]
        
        # Get full device region from SystemDict
        full_region = board_dict.full_device_region
        
        # Expand entire device to configuration bit addresses via ACME
        addresses = expand_device_to_config_bits(
            full_device_region=full_region,
            board_name=board_name,
            ebd_path=ebd_path
        )
        
        # Optional sampling to limit pool size
        sample_size = self.args.get("sample_size")
        if sample_size is not None:
            sample_size = int(sample_size)
            if len(addresses) > sample_size:
                addresses = self.rng.sample(addresses, sample_size)
        
        # Apply ordering mode
        mode = self.args.get("mode", "sequential")
        if mode == "shuffled":
            # Shuffle addresses before building pool
            self.rng.shuffle(addresses)
        elif mode == "random":
            # Random order (same as shuffled, just different name)
            self.rng.shuffle(addresses)
        # sequential mode: keep addresses in original order
        
        # Build pool with all addresses as CONFIG targets
        pool = TargetPool()
        for addr in addresses:
            pool.add(TargetSpec(
                kind=TargetKind.CONFIG,
                module_name="device",  # Device-wide (no specific module)
                config_address=addr,
                pblock_name=None,      # Device-wide (no specific pblock)
                source="profile:device"
            ))
        
        # Add ALL registers from ALL modules to pool
        for module_name, module_info in board_dict.modules.items():
            for reg_id in module_info.registers:
                # Find register name from board's register list
                reg_name = None
                for reg_info in board_dict.registers:
                    if reg_info.reg_id == reg_id:
                        reg_name = reg_info.name
                        break
                
                # Add register target to pool
                pool.add(TargetSpec(
                    kind=TargetKind.REG,
                    module_name=module_name,
                    reg_id=reg_id,
                    reg_name=reg_name,
                    source="profile:device",
                    tags=["register"]  # Tag to distinguish from CONFIG targets
                ))
        
        
        return pool