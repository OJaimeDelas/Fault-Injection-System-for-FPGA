# =============================================================================
# FATORI-V • FI ACME Cache
# File: fi/backend/acme/cache.py
# -----------------------------------------------------------------------------
# ACME cache path computation for device-wide and region-specific addresses.
#=============================================================================

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional


def _sanitize(name: str) -> str:
    """
    Make a filename-friendly token (letters, digits, '-', '_', '.').
    
    Args:
        name: String to sanitize
    
    Returns:
        Sanitized string safe for filenames
    """
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())


def cached_device_path(
    *,
    ebd_path: str | Path,
    board_name: str,
    cache_dir: str | Path | None = None
) -> Path:
    """
    Compute cache file path for device-wide addresses.
    
    This is used when generating addresses for the entire device without
    region filtering. The cache key includes board name, EBD filename,
    file size, modification time, and path hash to ensure cache validity.
    
    Filename format:
        {board}__{ebd_name}__{size}__{mtime}__{pathhash}.txt
    
    Args:
        ebd_path: Path to the source Vivado .ebd file
        board_name: Board key (e.g., "xcku040", "basys3")
        cache_dir: Cache directory (default: fi/build/acme)
    
    Returns:
        Path to cache file
    """
    ebd = Path(ebd_path)
    base = Path(cache_dir) if cache_dir else Path("gen") / "acme"
    
    # Get file metadata for cache validation
    try:
        st = ebd.stat()
        size = st.st_size
        mtime = int(st.st_mtime)
    except Exception:
        # If stat fails, use zeros (cache will likely miss)
        size = 0
        mtime = 0
    
    # Include absolute path in hash to disambiguate same-named copies
    try:
        abs_s = str(ebd.resolve())
    except Exception:
        abs_s = str(ebd)
    
    h = hashlib.sha1(abs_s.encode("utf-8")).hexdigest()[:8]
    fname = (
        f"{_sanitize(board_name.lower())}"
        f"__{_sanitize(ebd.name)}"
        f"__{size}"
        f"__{mtime:08X}"
        f"__{h}.txt"
    )
    return base / fname


def cached_region_path(
    *,
    ebd_path: str | Path,
    board_name: str,
    x_lo: int,
    y_lo: int,
    x_hi: int,
    y_hi: int,
    cache_dir: str | Path | None = None
) -> Path:
    """
    Compute cache file path for region-specific addresses.
    
    This is used when generating addresses for a specific pblock region.
    The cache key includes board name, EBD filename, and physical coordinates.
    This ensures that:
    - Same coordinates from different EBD files use different caches
    - Same module at different locations uses different caches
    - Different designs (different EBD) with same coordinates use different caches
    
    Filename format:
        {board}_{ebd_name}_{x_lo}_{y_lo}_{x_hi}_{y_hi}.txt
    
    IMPORTANT: The upper layer must ensure different designs generate different
    EBD filenames. If two different implementations use "design.ebd", they will
    incorrectly share cache entries for the same coordinates.
    
    Args:
        ebd_path: Path to the source Vivado .ebd file
        board_name: Board key (e.g., "xcku040", "basys3")
        x_lo: Minimum X coordinate (inclusive)
        y_lo: Minimum Y coordinate (inclusive)
        x_hi: Maximum X coordinate (inclusive)
        y_hi: Maximum Y coordinate (inclusive)
        cache_dir: Cache directory (default: fi/build/acme)
    
    Returns:
        Path to cache file
    """
    ebd = Path(ebd_path)
    base = Path(cache_dir) if cache_dir else Path("gen") / "acme"
    
    # Extract EBD basename without extension for cleaner cache names
    ebd_stem = ebd.stem  # filename without .ebd extension
    
    # Build cache filename with coordinates
    # Format: board_ebdname_x_lo_y_lo_x_hi_y_hi.txt
    fname = (
        f"{_sanitize(board_name.lower())}"
        f"_{_sanitize(ebd_stem)}"
        f"_{x_lo}_{y_lo}_{x_hi}_{y_hi}.txt"
    )
    
    return base / fname


def read_cached_addresses(cache_path: Path) -> Optional[list[str]]:
    """
    Read cached addresses from file.
    
    Args:
        cache_path: Path to cache file
    
    Returns:
        List of address strings, or None if cache doesn't exist or is invalid
    """
    if not cache_path.exists():
        return None
    
    try:
        with cache_path.open('r', encoding='utf-8') as f:
            addresses = [line.strip() for line in f if line.strip()]
        
        # Validate cache has content
        if not addresses:
            return None
        
        return addresses
    
    except Exception:
        # Any error reading cache, treat as miss
        return None


def write_cached_addresses(cache_path: Path, addresses: list[str]) -> bool:
    """
    Write addresses to cache file.
    
    Args:
        cache_path: Path to cache file
        addresses: List of address strings to cache
    
    Returns:
        True if write succeeded, False otherwise
    """
    try:
        # Create directory if needed
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write addresses, one per line
        with cache_path.open('w', encoding='utf-8') as f:
            for addr in addresses:
                f.write(f"{addr}\n")
        
        return True
    
    except Exception:
        return False