# =============================================================================
# FATORI-V • Fault Injection Framework
# File: fi/acme/acme_cache.py
# -----------------------------------------------------------------------------
# ACME cache path computation.
#
# Responsibility
#   • Compute a deterministic, collision-resistant cache file path for a given
#     (EBD file, board). The cache file stores one 10-hex LFA per line and is
#     used to avoid reparsing large .ebd files on subsequent runs.
#
# Policy
#   • The keyed cache lives under:  fi/build/acme/
#     This keeps implementation artifacts with the codebase rather than mixing
#     them with human-facing run results.
#   • Callers may override the base cache directory by passing 'cache_dir'.
#
# Filename scheme
#   • <board>__<ebd_basename>__<bytes>__<mtimehex>__<pathhash8>.txt
#       - board        : lowercased board key (e.g., xcku040, basys3)
#       - ebd_basename : original EBD filename (sanitized)
#       - bytes        : file size in bytes
#       - mtimehex     : file mtime encoded as hex integer (seconds resolution)
#       - pathhash8    : 8-hex hash of the absolute path to disambiguate copies
#
# Notes
#   • This module computes paths only; directory creation and file I/O are done
#     by the caller (see fi/acme/__init__.py).
# =============================================================================

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def _sanitize(name: str) -> str:
    """Make a filename-friendly token (letters, digits, '-', '_', '.')."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())


def cached_device_path(*, ebd_path: str | Path, board_name: str, cache_dir: str | Path | None) -> Path:
    """
    Compute the cache file path for the (ebd_path, board_name) pair.

    Parameters
    ----------
    ebd_path   : Path to the source Vivado .ebd file.
    board_name : User-provided board key (any casing); used in the filename.
    cache_dir  : Optional base directory. If None, defaults to 'fi/build/acme'.

    Returns
    -------
    Path to the cache file. Caller must ensure parent directories exist.
    """
    ebd = Path(ebd_path)
    # Default cache root lives under the repository, away from human-facing results
    base = Path(cache_dir) if cache_dir else Path("fi") / "build" / "acme"

    try:
        st = ebd.stat()
        size = st.st_size
        mtime = int(st.st_mtime)
    except Exception:
        # If stat fails, still create a stable-ish name
        size = 0
        mtime = 0

    # Include absolute path in the hash to disambiguate same-named copies
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
