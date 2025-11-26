# =============================================================================
# FATORI-V • Fault Injection Framework
# File: fi/acme/acme_xcku040.py
# -----------------------------------------------------------------------------
# Board/device map for XCKU040 (UltraScale) — used by KCU105 and AES-KU040.
#
# Purpose
#   • Provide device-level constants needed by the ACME engine and, later,
#     by region-aware filtering (pblocks).
#   • The device rectangle is given in physical *tile* coordinates, matching
#     Vivado’s Routing Resources grid (Column=X, Row=Y), as inspected by the
#     user on the AES-KU040 board:
#         X: 0 .. 358
#         Y: 0 .. 310
#
# Notes
#   • UltraScale frames have 123 words (WF=123). Many EBD dumps also include
#     header/dummy lines before the “real” per-frame lines; DUMMY=141 is kept
#     here to support future module filtering logic.
#   • This module keeps the interface minimal for the device-wide extractor.
# =============================================================================

from __future__ import annotations


class Xcku040Board:
    """
    Device map for the XCKU040 die used on KCU105 and AES-KU040 boards.

    Attributes
    ----------
    FAMILY : str
        Device family label; currently informational.
    WF : int
        Words per configuration frame (UltraScale: 123).
    DUMMY : int
        Header/dummy line count in certain EBD layouts (kept for future use).
    MIN_X, MAX_X, MIN_Y, MAX_Y : int
        Physical tile extents (inclusive).
    """

    FAMILY = "ultrascale"
    WF = 123
    DUMMY = 141

    # Physical tile extents observed in Vivado (Routing Resources tooltips)
    MIN_X = 0
    MAX_X = 358
    MIN_Y = 0
    MAX_Y = 310

    def full_device_rect(self) -> tuple[int, int, int, int]:
        """
        Return the (x_lo, y_lo, x_hi, y_hi) rectangle covering the whole device.
        """
        return (self.MIN_X, self.MIN_Y, self.MAX_X, self.MAX_Y)

    # Future geometry helpers for pblock filtering may be added here.
