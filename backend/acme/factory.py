# =============================================================================
# FATORI-V • FI ACME Factory
# File: fi/backend/acme/factory.py
# -----------------------------------------------------------------------------
# ACME engine factory and public API for address expansion with region filtering.
#=============================================================================

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Iterator, Tuple, List, Optional, Dict, Any

from fi.backend.acme.core import parse_ebd_to_lfas
from fi.backend.acme.cache import (
    cached_device_path,
    cached_region_path,
    read_cached_addresses,
    write_cached_addresses
)
from fi.backend.acme.geometry import unpack_lfa, rect_contains_point
from fi.backend.acme.xcku040 import Xcku040Board
from fi.backend.acme.basys3 import Basys3Board
from fi.core.logging.events import log_acme_cache_hit, log_acme_expansion

logger = logging.getLogger(__name__)


# ------------------------------ board loader ---------------------------------
def load_board(name: str):
    """
    Return a board/device map object by name. Names are case-insensitive.

    Supported aliases
    -----------------
    UltraScale KU040 family:
        "xcku040", "ku105", "kcu105", "aes-ku040", "aes_ku040", "aes-ku040-db"
    Artix-7 Basys3:
        "basys3", "xc7a35t", "xa35t", "arty-a35t", "a35t"
    """
    key = (name or "").strip().lower()
    if key in ("xcku040", "ku105", "kcu105", "aes-ku040", "aes_ku040", "aes-ku040-db"):
        return Xcku040Board()
    if key in ("basys3", "xc7a35t", "xa35t", "arty-a35t", "a35t"):
        return Basys3Board()
    raise ValueError(f"Unsupported board/device name: {name!r}")


def get_supported_boards() -> List[str]:
    """
    Return the canonical board names that the FI console is expected to accept.

    The mapping from CLI names to device maps can be richer (via aliases in
    load_board), but this helper lists the "nice" names that should usually
    appear in help texts and documentation.
    """
    return ["basys3", "xcku040"]


# ------------------------------ ACME engine ----------------------------------


class AcmeEngine:
    """
    ACME engine with region filtering support.

    Responsibilities
    ----------------
    • Keep track of a logical board name and the path to an EBD file.
    • Own the board/device map object (Basys3Board, Xcku040Board, …).
    • Provide high-level method expand_region_to_config_bits() that returns
      SEM LFAs (10-hex strings) for configuration bits within a specified
      physical region.
    • Cache filtered addresses to avoid expensive recomputation.

    Region Filtering
    ----------------
    • region_spec can be:
        - Dict with keys: x_lo, y_lo, x_hi, y_hi (physical coordinates)
        - None (returns device-wide addresses)
    • Filtering uses board-specific coordinate mapping (la_to_xy)
    • Results are cached based on (board, ebd_file, coordinates)
    """

    def __init__(self, board_name: str, ebd_path: str, cache_dir: str = "gen/acme") -> None:
        self.board_name: str = (board_name or "").strip()
        self.ebd_path: str = str(ebd_path)
        self._board = load_board(self.board_name)
        self.cache_dir = cache_dir

    def expand_region_to_config_bits(
        self,
        region_spec: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[str]:
        """
        Expand a region description into configuration-bit addresses.

        NOW IMPLEMENTS ACTUAL REGION FILTERING based on physical coordinates.
        Uses caching to avoid expensive recomputation.

        Parameters
        ----------
        region_spec:
            Region description with physical coordinates:
            - Dict with keys: x_lo, y_lo, x_hi, y_hi (all integers)
            - None for device-wide addresses (no filtering)
        
        use_cache:
            Whether to use cached results if available (default: True)

        Returns
        -------
        list[str]
            List of SEM LFAs (10-hex uppercase strings) that fall within
            the specified region (or all addresses if region_spec is None).

        Notes
        -----
        • Device-wide cache key: (board, ebd_file, size, mtime, path)
        • Region cache key: (board, ebd_file, x_lo, y_lo, x_hi, y_hi)
        • Filtering accuracy depends on board-specific la_to_xy() mapping
        """
        # Handle device-wide case (no filtering)
        if region_spec is None:
            return self._expand_device_wide(use_cache=use_cache)
        
        # Extract coordinates from region_spec
        try:
            x_lo = int(region_spec['x_lo'])
            y_lo = int(region_spec['y_lo'])
            x_hi = int(region_spec['x_hi'])
            y_hi = int(region_spec['y_hi'])
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Invalid region_spec: {e}")
            raise ValueError(
                f"region_spec must be dict with x_lo/y_lo/x_hi/y_hi or None, "
                f"got: {region_spec!r}"
            )
        
        logger.info(
            "ACME engine expanding region (%d,%d)-(%d,%d) for board '%s' using EBD '%s'.",
            x_lo, y_lo, x_hi, y_hi,
            self.board_name,
            self.ebd_path,
        )
        
        # Try cache first if enabled
        if use_cache:
            cache_path = cached_region_path(
                ebd_path=self.ebd_path,
                board_name=self.board_name,
                x_lo=x_lo,
                y_lo=y_lo,
                x_hi=x_hi,
                y_hi=y_hi,
                cache_dir=self.cache_dir
            )
            
            cached = read_cached_addresses(cache_path)
            if cached is not None:
                # Log cache hit using event logger (shows in console)
                region_str = f"[{x_lo},{y_lo},{x_hi},{y_hi}]"
                log_acme_cache_hit(region_str, len(cached))
                return cached
                        
            logger.debug(f"ACME cache miss: {cache_path.name}")
        
        # Cache miss or disabled - filter addresses by region
        addresses = self._filter_by_region(x_lo, y_lo, x_hi, y_hi)
        
        # Cache results if enabled and non-empty
        if use_cache and addresses:
            cache_path = cached_region_path(
                ebd_path=self.ebd_path,
                board_name=self.board_name,
                x_lo=x_lo,
                y_lo=y_lo,
                x_hi=x_hi,
                y_hi=y_hi,
                cache_dir=self.cache_dir
            )
            
            if write_cached_addresses(cache_path, addresses):
                logger.info(
                    "ACME cached %d addresses to %s",
                    len(addresses),
                    cache_path.name
                )
            else:
                logger.warning(f"Failed to write ACME cache: {cache_path}")
        
        # Log expansion using event logger (shows in console)
        region_str = f"[{x_lo},{y_lo},{x_hi},{y_hi}]"
        log_acme_expansion(region_str, len(addresses))

        return addresses
    
    def _expand_device_wide(self, use_cache: bool = True) -> List[str]:
        """
        Generate device-wide addresses (no region filtering).
        
        Args:
            use_cache: Whether to use cached results
        
        Returns:
            List of all device addresses
        """
        logger.info(
            "ACME engine expanding device-wide for board '%s' using EBD '%s'.",
            self.board_name,
            self.ebd_path,
        )
        
        # Try cache first if enabled
        if use_cache:
            cache_path = cached_device_path(
                ebd_path=self.ebd_path,
                board_name=self.board_name,
                cache_dir=self.cache_dir
            )
            
            cached = read_cached_addresses(cache_path)
            if cached is not None:
                # Log cache hit using event logger (shows in console)
                log_acme_cache_hit("device-wide", len(cached))
                return cached
        
        # Cache miss or disabled - parse EBD
        addresses: List[str] = []
        for lfa in extract_device_addresses(self.ebd_path, self._board):
            addresses.append(str(lfa).strip().upper())
        
        # Cache results if enabled and non-empty
        if use_cache and addresses:
            cache_path = cached_device_path(
                ebd_path=self.ebd_path,
                board_name=self.board_name,
                cache_dir=self.cache_dir
            )
            
            if write_cached_addresses(cache_path, addresses):
                logger.info(
                    "ACME cached %d device-wide addresses to %s",
                    len(addresses),
                    cache_path.name
                )
        
        # Log expansion using event logger (shows in console)
        log_acme_expansion("device-wide", len(addresses))

        return addresses
    
    def _filter_by_region(self, x_lo: int, y_lo: int, x_hi: int, y_hi: int) -> List[str]:
        """
        Filter device addresses to only those within specified region.
        
        Args:
            x_lo, y_lo: Minimum coordinates (inclusive)
            x_hi, y_hi: Maximum coordinates (inclusive)
        
        Returns:
            List of addresses within region
        """
        addresses: List[str] = []
        filtered_count = 0
        total_count = 0
        
        for lfa in extract_device_addresses(self.ebd_path, self._board):
            total_count += 1
            
            try:
                # Unpack LFA to get linear frame address
                la, word, bit = unpack_lfa(lfa)
                
                # Map to physical coordinates
                x, y = self._board.la_to_xy(la)
                
                # Check if within region bounds
                if rect_contains_point(x, y, x_lo, y_lo, x_hi, y_hi):
                    addresses.append(str(lfa).strip().upper())
                else:
                    filtered_count += 1
            
            except Exception as e:
                # Log and skip invalid LFAs
                logger.debug(f"Skipping invalid LFA {lfa}: {e}")
                continue
        
        logger.debug(
            f"Filtered {filtered_count} of {total_count} addresses "
            f"({100.0 * filtered_count / max(1, total_count):.1f}% reduction)"
        )
        
        return addresses


def make_acme_engine(
    *,
    board_name: str,
    ebd_path: str,
    cache_dir: str = "gen/acme"
) -> "AcmeEngine":
    """
    Factory helper that constructs an :class:`AcmeEngine`.

    Parameters
    ----------
    board_name:
        Logical board key, following the same conventions as load_board.
    ebd_path:
        Path to the Vivado essential-bits (.ebd) file.

    Returns
    -------
    AcmeEngine
        Ready-to-use engine that can be passed to the targets layer.

    Notes
    -----
    • load_board() is used internally to validate the board name. A
      ValueError will surface configuration mistakes early.
    """
    board_name = (board_name or "").strip()
    if not board_name:
        raise ValueError("Board name is empty when constructing ACME engine.")
    if not ebd_path:
        raise ValueError("EBD path is empty when constructing ACME engine.")

    # Validate the board name quickly
    load_board(board_name)

    logger.info(
        "Initialising ACME engine for board '%s' with EBD file '%s'.",
        board_name,
        ebd_path,
    )
    return AcmeEngine(board_name=board_name, ebd_path=ebd_path, cache_dir=cache_dir)


# ------------------------------ debug helpers --------------------------------


def _env_truthy(var_name: str, default: bool = False) -> bool:
    """True if env var is one of: 1, true, yes, on (case-insensitive)."""
    val = os.environ.get(var_name, "")
    if not val:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def scan_ebd_payload_stats(ebd_path: str | Path) -> Tuple[int, int, int]:
    """
    Lightweight pre-scan to help diagnose empty-device situations.

    Returns
    -------
    tuple: (payload_rows, full_32bit_words, ones_bits)
      • payload_rows     : number of lines that contain only 0/1 and whitespace.
      • full_32bit_words : number of complete 32-bit words seen when collapsing
                           those rows and chunking per 32 bits.
      • ones_bits        : total number of '1' bits across all complete words.

    Notes
    -----
    • Streaming scan; trailing partial (<32-bit) chunks are ignored.
    • Mirrors the parser's treatment of payload rows.
    """
    from re import compile as _re

    p = Path(ebd_path)
    payload_rows = 0
    full_words = 0
    ones = 0
    re_payload = _re(r"^[01\s\t]+$")
    with p.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if re_payload.match(line):
                payload_rows += 1
                bits = "".join(ch for ch in line if ch in "01")
                n_full = len(bits) // 32
                full_words += n_full
                if "1" in bits:
                    for i in range(n_full):
                        chunk = bits[i * 32 : (i + 1) * 32]
                        if "1" in chunk:
                            ones += chunk.count("1")
    return payload_rows, full_words, ones


# ------------------------------ device extract -------------------------------


def extract_device_addresses(ebd_path: str | Path, board) -> Iterator[str]:
    """Stream SEM LFAs (10-hex strings) parsed from an EBD file."""
    return parse_ebd_to_lfas(ebd_path, board)


def get_or_build_cached_device_list(
    *,
    ebd_path: str | Path,
    board_name: str,
    cache_dir: str | Path,
) -> Path:
    """
    Build (or reuse) a cached device-wide address list under cache_dir.
    The cache key includes the board name and the EBD file hash/mtime.

    Debug (FI_ACME_DEBUG)
    ---------------------
    Prints: EBD path and size; payload stats; first few LFAs emitted (N controlled
    by FI_ACME_DEBUG_N; default 5).
    """
    ebd_path = Path(ebd_path)
    cache_path = cached_device_path(ebd_path=ebd_path, board_name=board_name, cache_dir=cache_dir)

    debug = _env_truthy("FI_ACME_DEBUG", False)
    debug_n = int(os.environ.get("FI_ACME_DEBUG_N", "5") or "5")
    force_rebuild = _env_truthy("FI_ACME_REBUILD", False)

    if debug:
        from fi.core.logging.events import log_acme_debug
        try:
            stat = ebd_path.stat()
            log_acme_debug("ebd_stat", path=str(ebd_path), size=f"{stat.st_size} bytes")
        except Exception:
            log_acme_debug("ebd_stat", path=str(ebd_path), size="<stat failed>")
        pr, fw, ones = scan_ebd_payload_stats(ebd_path)
        log_acme_debug("payload_stats", rows=pr, words=fw, ones=ones)

    # Fast path: reuse cache unless forced to rebuild or file is empty
    if cache_path.exists() and not force_rebuild:
        cached = read_cached_addresses(cache_path)
        if cached is not None:
            if debug:
                log_acme_debug("cache_hit", path=str(cache_path), lines=len(cached))
            return cache_path

    board = load_board(board_name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    emitted = 0
    samples: list[str] = []

    addresses = []
    for lfa in extract_device_addresses(ebd_path, board):
        addresses.append(lfa)
        emitted += 1
        if debug and len(samples) < max(0, debug_n):
            samples.append(lfa)

    write_cached_addresses(cache_path, addresses)

    if debug:
        log_acme_debug("emit_complete", count=emitted, path=str(cache_path))
        if samples:
            log_acme_debug("samples", samples=samples)

    # Defensive: if emitted==0, remove the empty cache so callers can detect it
    if emitted == 0:
        try:
            cache_path.unlink()
        except Exception:
            pass

    return cache_path