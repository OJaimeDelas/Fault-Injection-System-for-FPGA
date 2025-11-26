# =============================================================================
# FATORI-V • FI ACME Factory
# File: acme_factory.py
# -----------------------------------------------------------------------------
# ACME engine factory and public API for address expansion.
#=============================================================================

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Iterator, Tuple, List

from fi.backend.acme.core import parse_ebd_to_lfas
from fi.backend.acme.cache import cached_device_path
from fi.backend.acme.xcku040 import Xcku040Board
from fi.backend.acme.basys3 import Basys3Board

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
    # The aliases understood by load_board() are intentionally *not* all
    # repeated here; this list is meant for user-facing documentation and
    # validation, not for parsing every possible spelling.
    return ["basys3", "xcku040"]


# ------------------------------ ACME engine ----------------------------------


class AcmeEngine:
    """
    Minimal ACME engine wrapper.

    Responsibilities
    ----------------
    • Keep track of a logical board name and the path to an EBD file.
    • Own the board/device map object (Basys3Board, Xcku040Board, …).
    • Provide a single high-level method:
          expand_region_to_config_bits(region_spec) -> list[str]
      that returns SEM LFAs (10-hex strings) for configuration bits that
      belong to the region of interest.

    Region semantics
    ----------------
    • The shape of 'region_spec' is deliberately opaque at this level. It is
      whatever the targets layer / system dictionary uses to describe a pblock
      region (for example, a tile rectangle or frame range).
    • The current implementation *accepts and logs* the region spec but does
      not yet filter geometrically; it emits device-wide addresses derived
      from the EBD file. This keeps the public API stable while allowing
      region-aware filtering to be implemented later without touching callers.
    """

    def __init__(self, board_name: str, ebd_path: str) -> None:
        self.board_name: str = (board_name or "").strip()
        # Store the EBD path as a string for logging and reproducibility.
        self.ebd_path: str = str(ebd_path)
        # Resolve the concrete board/device map; this validates the name early.
        self._board = load_board(self.board_name)

    def expand_region_to_config_bits(self, region_spec) -> List[str]:
        """
        Expand a region description into configuration-bit addresses.

        Parameters
        ----------
        region_spec:
            Opaque region description coming from the system dictionary. The
            current implementation does not interpret it geometrically and
            simply emits all device-wide essential bits for the EBD.

        Returns
        -------
        list[str]
            List of SEM LFAs (10-hex uppercase strings), suitable for feeding
            into SEM or wrapping in TargetSpec objects.

        Notes
        -----
        • The engine hides all details of the EBD → (LA, WORD, BIT) mapping by
          deferring to parse_ebd_to_lfas via extract_device_addresses.
        • Future versions can add optional sampling or region filtering here
          without changing the targets layer API.
        """
        logger.info(
            "ACME engine expanding region %r for board '%s' using EBD '%s'.",
            region_spec,
            self.board_name,
            self.ebd_path,
        )

        addresses: List[str] = []

        # Streaming parse of the EBD file. The underlying parser already
        # encapsulates the mapping from payload words to (LA, WORD, BIT).
        for lfa in extract_device_addresses(self.ebd_path, self._board):
            # Normalise as uppercase hex string to keep logs and YAML dumps
            # consistent, even if the parser ever returns lowercase.
            addresses.append(str(lfa).strip().upper())

        logger.info(
            "ACME engine produced %d configuration-bit addresses for region %r.",
            len(addresses),
            region_spec,
        )
        return addresses


def make_acme_engine(board_name: str, ebd_path: str) -> AcmeEngine:
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

    # Validate the board name quickly; AcmeEngine will call load_board again
    # but the early check makes the error message in logs more explicit.
    load_board(board_name)

    logger.info(
        "Initialising ACME engine for board '%s' with EBD file '%s'.",
        board_name,
        ebd_path,
    )
    return AcmeEngine(board_name=board_name, ebd_path=ebd_path)


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
        try:
            stat = ebd_path.stat()
            print(f"[DEBUG][ACME] EBD: {ebd_path} — size={stat.st_size} bytes")
        except Exception:
            print(f"[DEBUG][ACME] EBD: {ebd_path} — <stat failed>")
        pr, fw, ones = scan_ebd_payload_stats(ebd_path)
        print(f"[DEBUG][ACME] payload_rows={pr}, full_32bit_words={fw}, ones_bits={ones}")

    # Fast path: reuse cache unless forced to rebuild or file is empty
    if cache_path.exists() and not force_rebuild:
        try:
            with cache_path.open("r", encoding="utf-8", errors="ignore") as fh:
                # Peek two lines: 0 -> empty file; 1+ -> usable
                first = fh.readline()
                second = fh.readline()
                has_data = bool(first or second)
        except Exception:
            has_data = False

        if has_data:
            if debug:
                try:
                    n_lines = sum(
                        1 for _ in cache_path.open("r", encoding="utf-8", errors="ignore")
                    )
                except Exception:
                    n_lines = -1
                print(f"[DEBUG][ACME] cache hit: {cache_path} (lines={n_lines})")
            return cache_path
        else:
            # Stale/empty cache — remove and rebuild
            try:
                cache_path.unlink()
                if debug:
                    print(f"[DEBUG][ACME] removed empty cache: {cache_path}")
            except Exception:
                pass

    board = load_board(board_name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    emitted = 0
    samples: list[str] = []

    with cache_path.open("w", encoding="utf-8") as fh:
        for lfa in extract_device_addresses(ebd_path, board):
            fh.write(lfa + "\n")
            emitted += 1
            if debug and len(samples) < max(0, debug_n):
                samples.append(lfa)

    if debug:
        print(f"[DEBUG][ACME] emitted={emitted} LFAs → {cache_path}")
        if samples:
            print("[DEBUG][ACME] first LFAs:", ", ".join(samples))

    # Defensive: if emitted==0, remove the empty cache so callers can detect it
    if emitted == 0:
        try:
            cache_path.unlink()
        except Exception:
            pass