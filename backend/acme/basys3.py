# =============================================================================
# FATORI-V • Fault Injection Framework
# File: fi/acme/acme_basys3.py
# -----------------------------------------------------------------------------
# Board/device map for Basys3 (Artix-7, XC7A35T).
#
# Purpose
#   • Provide minimal device constants so the ACME extractor can convert
#     Essential Bits Data (.ebd) entries into SEM injection addresses (LFAs).
#   • Geometry (tile extents) is included for completeness and future region
#     filtering, but the current device-wide extraction path does not depend on
#     these values.
#
# Interface
#   • FAMILY : Device family label ("7series").
#   • WF    : Words per configuration frame (7-Series: 101).
#   • DUMMY : Header/dummy line count present in some EBD layouts (kept for
#             future use by region filtering; not used by device-wide flow).
#   • MIN_X, MAX_X, MIN_Y, MAX_Y : Physical tile extents (inclusive).
#   • full_device_rect() : Convenience to return the full tile rectangle.
# =============================================================================

from __future__ import annotations


class Basys3Board:
    """
    Device map for the Artix-7 XC7A35T used on the Basys3 board.

    Notes
    -----
    • The current ACME device-wide extraction path uses WF and does not require
      geometry; the tile extents are provided here for future module (pblock)
      filtering logic.
    """

    FAMILY = "7series"
    WF = 101
    DUMMY = 109

    # Physical tile extents (inclusive). These bounds are safe for device-wide
    # address extraction and will be refined/used by module filtering later.
    MIN_X = 0
    MAX_X = 209
    MIN_Y = 0
    MAX_Y = 159

    def full_device_rect(self) -> tuple[int, int, int, int]:
        """
        Return the (x_lo, y_lo, x_hi, y_hi) rectangle covering the whole device.
        """
        return (self.MIN_X, self.MIN_Y, self.MAX_X, self.MAX_Y)
