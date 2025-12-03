# =============================================================================
# FATORI-V • Fault Injection Framework
# File: fi/acme/acme_core.py
# -----------------------------------------------------------------------------
# ACME core: converts Vivado Essential Bits Data (.ebd) into SEM injection
# addresses (LFAs).
#
# Responsibilities
#   • Parse EBD in two common layouts and emit 10-hex-digit LFAs:
#       (A) Token format lines that already encode locations:
#           • a standalone 10-hex LFA token; or
#           • FAR/WORD/BIT named triples (order-independent); or
#           • “frame <..> word <..> bit <..>” sequences.
#       (B) ASCII-bitstream format (“Xilinx ASCII Bitstream … Type: essential”)
#           whose payload rows contain only 0/1 (sometimes with spaces). These
#           rows represent a linear stream of 32-bit words. Each 32-bit word is
#           mapped to (LA, WORD) using the device’s words-per-frame (WF), then
#           an LFA is emitted for every '1' bit: BIT = 31 - column_index (MSB left).
#
# Mapping for ASCII-bitstream (device-wide)
#   • Let WF = board.WF (words per frame). For UltraScale WF=123; for 7-Series WF=101.
#   • The 0/1 word stream encodes payload words; mapping:
#         LA   = W // WF
#         WORD = W %  WF
#         BIT  = 31 - column_index
#         LFA  = (LA << 12) | (WORD << 5) | BIT
#
# Notes
#   • Blank lines and human-readable headers are ignored. A blank line between
#     the header and the first 0/1 data row is accepted (ignored).
#   • The parser works in a streaming fashion; the entire file is not loaded.
#   • This module performs no geometric/pblock filtering; it is device-wide.
# =============================================================================

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator, Optional


# --------------------------- helpers: packing --------------------------------

def _pack_lfa(la: int, word: int, bit: int) -> str:
    """
    Pack LA/WORD/BIT into a 40-bit SEM LFA and return it as 10 hex digits.

    LA    : linear frame address (non-negative integer)
    WORD  : index within the frame (0..127; WF must not exceed 128)
    BIT   : index within the word (0..31)

    Raises ValueError if any field is out of range.
    """
    if la < 0 or word < 0 or bit < 0:
        raise ValueError("Negative LA/WORD/BIT not allowed")
    if bit > 31:
        raise ValueError("BIT out of range (0..31)")
    if word > 127:
        # 7 bits available in the chosen packing; WF should not exceed 128.
        raise ValueError("WORD out of range (0..127)")
    val = (int(la) << 12) | (int(word) << 5) | int(bit)
    return f"{val:010X}"


# ----------------------------- EBD parsing -----------------------------------

# Accept a standalone 10-hex token (already an LFA)
_RE_LFA = re.compile(r"\b([0-9A-Fa-f]{10})\b")

# Accept FAR/WORD/BIT named fields, order-independent (useful for some exports)
_RE_FAR = re.compile(r"\b(FAR|FRAME)\s*[:=]\s*(0x[0-9A-Fa-f]+|\d+)\b", re.IGNORECASE)
_RE_WRD = re.compile(r"\b(WORD|WD)\s*[:=]\s*(\d+)\b", re.IGNORECASE)
_RE_BIT = re.compile(r"\b(BIT|BT)\s*[:=]\s*(\d+)\b", re.IGNORECASE)

# Accept patterns like: frame 0xABCDE, word 12, bit 3
_RE_FRAME_WORD_BIT = re.compile(
    r"\bframe\s*(0x[0-9A-Fa-f]+|\d+)\b.*?\bword\s*(\d+)\b.*?\bbit\s*(\d+)\b",
    re.IGNORECASE,
)

# Accept payload rows made entirely of 0/1 plus optional spaces/tabs
# (typical "ASCII Bitstream / Type: essential" data lines).
_RE_BINLINE_ANY = re.compile(r"^[01\s\t]+$")

# Exact 32-bit word (no spaces) — fast-path.
_RE_BIN32 = re.compile(r"^[01]{32}$")


def _maybe_int(token: str) -> Optional[int]:
    try:
        if token.lower().startswith("0x"):
            return int(token, 16)
        return int(token, 10)
    except Exception:
        return None


def _extract_token_lfa(line: str) -> Optional[str]:
    """
    Token-based extractor:
      1) direct 10-hex token (assumed to be a valid LFA already),
      2) FAR/WORD/BIT named fields (order-independent),
      3) 'frame <..> word <..> bit <..>' pattern.
    Returns a 10-hex LFA if recognized; otherwise None.
    """
    # Strategy 1: direct LFA token
    m = _RE_LFA.search(line)
    if m:
        return m.group(1).upper()

    # Strategy 2: named tokens anywhere in the line
    far = _RE_FAR.search(line)
    wrd = _RE_WRD.search(line)
    bit = _RE_BIT.search(line)
    if far and wrd and bit:
        f = _maybe_int(far.group(2))
        w = _maybe_int(wrd.group(2))
        b = _maybe_int(bit.group(2))
        if f is not None and w is not None and b is not None:
            return _pack_lfa(f, w, b)

    # Strategy 3: ordered keywords (frame, word, bit)
    m2 = _RE_FRAME_WORD_BIT.search(line)
    if m2:
        f2 = _maybe_int(m2.group(1))
        w2 = _maybe_int(m2.group(2))
        b2 = _maybe_int(m2.group(3))
        if f2 is not None and w2 is not None and b2 is not None:
            return _pack_lfa(f2, w2, b2)

    return None


def _emit_word_bits(la: int, word: int, word_bits: str) -> Iterator[str]:
    """
    Emit LFAs for every '1' in a 32-character string of '0'/'1'.
    Interprets the string MSB→LSB; thus BIT = 31 - column_index.
    """
    if "1" not in word_bits:
        return
    for col, ch in enumerate(word_bits):
        if ch == "1":
            bit = 31 - col
            yield _pack_lfa(la, word, bit)


def parse_ebd_to_lfas(ebd_path: str | Path, board) -> Iterator[str]:
    """
    Parse an EBD text file and yield SEM LFAs (10-hex strings) for *all*
    essential bits described within.

    Behavior
    --------
    • If a line matches a tokenized format (10-hex LFA or FAR/WORD/BIT), it is
      parsed immediately and yields an address.
    • Otherwise, if a line consists solely of 0/1 (spaces/tabs allowed), it is
      treated as one or more 32-bit words:
        - exact 32 chars: a single word;
        - longer: spaces are removed and the string is split into consecutive
          32-bit chunks; any trailing <32-bit remainder is ignored.
      Each 32-bit word increments the *payload word index* W and maps to:
            LA = W // WF     • WORD = W % WF     • BIT = 31 - column_index
      For every '1' bit, an LFA is emitted.
    • Non-matching lines (headers) are ignored and do not increment W.
    • The function is streaming; it does not load the entire file in memory.

    Debug
    -----
    If FI_ACME_DEBUG is truthy in the environment, a few sample data points are
    printed the first times we encounter '1' bits:
      • the payload word index W, computed (LA, WORD), and up to FI_ACME_DEBUG_N
        sample LFAs for that word (default N=3 for this inner sampler).
    """
    p = Path(ebd_path)
    if not p.exists():
        raise FileNotFoundError(f"EBD file not found: {p}")

    # Words per frame is mandatory to interpret payload rows
    try:
        wf = int(getattr(board, "WF"))
        if wf <= 0 or wf > 128:
            raise ValueError
    except Exception:
        raise ValueError("Invalid board.WF; expected 1..128")

    word_index = 0  # counts only 32-bit payload words

    # Debug knobs
    dbg_enabled = str(os.environ.get("FI_ACME_DEBUG", "")).strip().lower() in ("1", "true", "yes", "on")
    dbg_inner_n = 3
    try:
        dbg_inner_n = max(0, int(os.environ.get("FI_ACME_DEBUG_INNER_N", "3")))
    except Exception:
        dbg_inner_n = 3
    dbg_shown = 0
    dbg_max_shows = 5  # limit inner prints to avoid flooding

    with p.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                # Blank header lines are fine and ignored.
                continue

            # Try token formats first (already-encoded addresses)
            lfa_tok = _extract_token_lfa(line)
            if lfa_tok:
                # Tokens take precedence; they do not use WF/word_index mapping.
                if dbg_enabled and dbg_shown < dbg_max_shows:
                    from fi.core.logging.events import log_acme_debug
                    log_acme_debug("token", lfa=lfa_tok)
                    dbg_shown += 1
                yield lfa_tok
                continue

            # Lines that contain only 0/1 (spaces allowed) are payload carriers
            if _RE_BIN32.match(line):
                la = word_index // wf
                word = word_index % wf
                # Gather a few sample LFAs for debug if there are '1's
                if dbg_enabled and dbg_shown < dbg_max_shows and "1" in line:
                    samples = []
                    for col, ch in enumerate(line):
                        if ch == "1":
                            bit = 31 - col
                            samples.append(_pack_lfa(la, word, bit))
                            if len(samples) >= dbg_inner_n:
                                break
                    if samples:
                        from fi.core.logging.events import log_acme_debug
                        log_acme_debug("word", word_index=word_index, la=la, word=word, samples=samples)
                        dbg_shown += 1
                # Emit all bits
                for lfa in _emit_word_bits(la, word, line):
                    yield lfa
                word_index += 1
                continue

            if _RE_BINLINE_ANY.match(line):
                bits = "".join(ch for ch in line if ch in "01")
                # Split into 32-bit chunks; ignore any trailing remainder
                n_full = len(bits) // 32
                for i in range(n_full):
                    chunk = bits[i * 32 : (i + 1) * 32]
                    la = word_index // wf
                    word = word_index % wf
                    if dbg_enabled and dbg_shown < dbg_max_shows and "1" in chunk:
                        samples = []
                        for col, ch in enumerate(chunk):
                            if ch == "1":
                                bit = 31 - col
                                samples.append(_pack_lfa(la, word, bit))
                                if len(samples) >= dbg_inner_n:
                                    break
                        if samples:
                            from fi.core.logging.events import log_acme_debug
                            log_acme_debug("word", word_index=word_index, la=la, word=word, samples=samples)
                            dbg_shown += 1
                    for lfa in _emit_word_bits(la, word, chunk):
                        yield lfa
                    word_index += 1
                continue

            # Ignore any other headers/lines
