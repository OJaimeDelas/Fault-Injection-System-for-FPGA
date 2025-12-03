# =============================================================================
# FATORI-V • FI Backend ACME
# File: decoder.py
# -----------------------------------------------------------------------------
# High-level ACME decoder interface for area profiles.
#=============================================================================

import logging
from typing import List, Optional, Dict

from fi.core.logging.events import log_acme_expansion, log_error

logger = logging.getLogger(__name__)


def expand_pblock_to_config_bits(
    region: Dict[str, int],
    board_name: str,
    ebd_path: str,
    use_cache: bool = True,
    cache_dir: str = "gen/acme"
) -> List[str]:
    """
    Convert pblock region coordinates to configuration bit addresses.
    
    This is the main ACME entry point for area profiles. The ACME engine
    is created on-demand, performs the expansion, and is discarded. No
    global state or setup is required.
    
    Args:
        region: Dict with coordinates {'x_lo': int, 'y_lo': int, 'x_hi': int, 'y_hi': int}
        board_name: Board name (e.g., "basys3", "xcku040")
        ebd_path: Path to .ebd essential bits file
    
    Returns:
        List of LFA address strings (e.g., ["00001234", "00001236", ...])
        Returns empty list on error (errors are logged)
    
    Notes:
        - ACME engine is created on-demand internally
        - No global state or persistent engine instance
        - Addresses are returned as uppercase hex strings
        - Empty list returned on any error (check logs for details)
    
    Example:
        >>> region = {'x_lo': 50, 'y_lo': 50, 'x_hi': 75, 'y_hi': 65}
        >>> addresses = expand_pblock_to_config_bits(
        ...     region=region,
        ...     board_name="xcku040",
        ...     ebd_path="backend/acme/design.ebd"
        ... )
        >>> len(addresses)
        1250
        >>> addresses[0]
        '00001234'
    """
    from fi.backend.acme.factory import make_acme_engine
    
    # Create ACME engine on-demand for this board/EBD combination
    try:
        engine = make_acme_engine(
            board_name=board_name,
            ebd_path=ebd_path,
            cache_dir=cache_dir
        )
    except Exception as e:
        log_error(f"Failed to create ACME engine for board '{board_name}'", exc=e)
        return []

    # Expand region to configuration bit addresses
    try:
        addresses = engine.expand_region_to_config_bits(region, use_cache=use_cache)
    except Exception as e:
        log_error(f"ACME expansion failed for region {region}", exc=e)
        return []

    return addresses


def expand_device_to_config_bits(
    device_coords: Dict[str, int],
    board_name: str,
    ebd_path: str,
    use_cache: bool = True,
    cache_dir: str = "gen/acme"
) -> List[str]:
    """
    Expand entire device region to configuration bit addresses.
    
    Used by 'device' area profile for device-wide injection. This is
    simply a convenience wrapper around expand_pblock_to_config_bits()
    with a more descriptive name for device-wide expansion.
    
    Args:
        device_coords: Dict with full device bounds {'x_lo': int, 'y_lo': int, 'x_hi': int, 'y_hi': int}
        board_name: Board name (e.g., "basys3", "xcku040")
        ebd_path: Path to .ebd essential bits file
    
    Returns:
        List of LFA address strings for entire device
        Returns empty list on error (errors are logged)
    
    Example:
        >>> device_coords = {'x_lo': 0, 'y_lo': 0, 'x_hi': 358, 'y_hi': 310}
        >>> addresses = expand_device_to_config_bits(
        ...     device_coords=device_coords,
        ...     board_name="xcku040",
        ...     ebd_path="backend/acme/design.ebd"
        ... )
        >>> len(addresses)
        45000  # Entire device has many addresses
    """
    # Forward directly to pblock expansion - same mechanism
    return expand_pblock_to_config_bits(
        device_coords, 
        board_name, 
        ebd_path, 
        use_cache=use_cache,
        cache_dir=cache_dir
    )