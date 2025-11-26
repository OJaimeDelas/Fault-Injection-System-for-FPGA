# =============================================================================
# FATORI-V • FI Targets
# File: acme_sem_decoder.py
# -----------------------------------------------------------------------------
# Clean ACME interface for area profiles to expand regions to addresses.
#=============================================================================

from typing import List
import logging

from fi.core.logging.events import log_acme_expansion, log_error

logger = logging.getLogger(__name__)


def expand_pblock_to_config_bits(
    region: str,
    board_name: str,
    ebd_path: str
) -> List[str]:
    """
    Convert pblock region coordinates to configuration bit addresses.
    
    This is the main ACME entry point for area profiles. The ACME engine
    is created on-demand, performs the expansion, and is discarded. No
    global state or setup is required.
    
    Args:
        region: Region string (e.g., "CLOCKREGION_X1Y2:CLOCKREGION_X1Y3")
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
        >>> addresses = expand_pblock_to_config_bits(
        ...     region="CLOCKREGION_X1Y2:CLOCKREGION_X1Y3",
        ...     board_name="xcku040",
        ...     ebd_path="fi/acme/design.ebd"
        ... )
        >>> len(addresses)
        1250
        >>> addresses[0]
        '00001234'
    """
    from fi.backend.acme.factory import make_acme_engine
    
    # Create ACME engine on-demand for this board/EBD combination
    try:
        engine = make_acme_engine(board_name=board_name, ebd_path=ebd_path)
    except Exception as e:
        log_error(f"Failed to create ACME engine for board '{board_name}'", exc=e)
        logger.error(f"Failed to create ACME engine for board '{board_name}': {e}")
        return []
    
    # Expand region to configuration bit addresses
    try:
        addresses = engine.expand_region_to_config_bits(region)
    except Exception as e:
        log_error(f"ACME expansion failed for region {region}", exc=e)
        logger.error(f"ACME expansion failed for region {region}: {e}")
        return []
    
    # Log successful expansion
    log_acme_expansion(region, len(addresses))
    
    logger.info(
        f"ACME expanded region {region} to {len(addresses)} config bits"
    )
    
    return addresses


def expand_device_to_config_bits(
    full_device_region: str,
    board_name: str,
    ebd_path: str
) -> List[str]:
    """
    Expand entire device region to configuration bit addresses.
    
    Used by 'device' area profile for device-wide injection. This is
    simply a convenience wrapper around expand_pblock_to_config_bits()
    with a more descriptive name for device-wide expansion.
    
    Args:
        full_device_region: Full device region string from SystemDict
        board_name: Board name (e.g., "basys3", "xcku040")
        ebd_path: Path to .ebd essential bits file
    
    Returns:
        List of LFA address strings for entire device
        Returns empty list on error (errors are logged)
    
    Example:
        >>> addresses = expand_device_to_config_bits(
        ...     full_device_region="CLOCKREGION_X0Y0:CLOCKREGION_X8Y8",
        ...     board_name="xcku040",
        ...     ebd_path="fi/acme/design.ebd"
        ... )
        >>> len(addresses)
        45000  # Entire device has many more addresses
    """
    return expand_pblock_to_config_bits(
        region=full_device_region,
        board_name=board_name,
        ebd_path=ebd_path
    )