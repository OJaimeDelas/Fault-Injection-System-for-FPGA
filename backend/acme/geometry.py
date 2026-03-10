# =============================================================================
# FATORI-V • FI ACME Geometry
# File: fi/backend/acme/geometry.py
# -----------------------------------------------------------------------------
# Coordinate mapping and geometric filtering for FPGA configuration frames.
#=============================================================================

from typing import Tuple


def unpack_lfa(lfa: str) -> Tuple[int, int, int]:
    """
    Unpack 10-hex LFA string into (LA, WORD, BIT) components.
    
    LFA format (40 bits):
        LA[28:12]   - Linear frame address (17 bits)
        WORD[11:5]  - Word within frame (7 bits, 0-127)
        BIT[4:0]    - Bit within word (5 bits, 0-31)
    
    Args:
        lfa: 10-character hex string (e.g., "00001234AB")
    
    Returns:
        Tuple of (la, word, bit) as integers
    
    Raises:
        ValueError: If LFA format is invalid
    """
    if not isinstance(lfa, str) or len(lfa) != 10:
        raise ValueError(f"LFA must be 10-character hex string, got: {lfa!r}")
    
    try:
        lfa_int = int(lfa, 16)
    except ValueError:
        raise ValueError(f"LFA contains invalid hex characters: {lfa!r}")
    
    # Extract bit fields from packed 40-bit value
    bit = lfa_int & 0x1F                # Bits [4:0]
    word = (lfa_int >> 5) & 0x7F        # Bits [11:5]
    la = (lfa_int >> 12)                # Bits [39:12]
    
    return (la, word, bit)


def pack_lfa(la: int, word: int, bit: int) -> str:
    """
    Pack (LA, WORD, BIT) components into 10-hex LFA string.
    
    Inverse of unpack_lfa(). Useful for testing and verification.
    
    Args:
        la: Linear frame address (non-negative)
        word: Word index within frame (0-127)
        bit: Bit index within word (0-31)
    
    Returns:
        10-character uppercase hex string
    
    Raises:
        ValueError: If any component is out of valid range
    """
    if la < 0:
        raise ValueError(f"LA must be non-negative, got {la}")
    if not 0 <= word <= 127:
        raise ValueError(f"WORD must be 0-127, got {word}")
    if not 0 <= bit <= 31:
        raise ValueError(f"BIT must be 0-31, got {bit}")
    
    # Pack into 40-bit value
    lfa_int = (la << 12) | (word << 5) | bit
    
    # Format as 10-character hex string
    return f"{lfa_int:010X}"


def rect_contains_point(x: int, y: int, x_lo: int, y_lo: int, x_hi: int, y_hi: int) -> bool:
    """
    Check if point (x, y) is within rectangle bounds (inclusive).
    
    Args:
        x: Point X coordinate
        y: Point Y coordinate
        x_lo: Rectangle minimum X (inclusive)
        y_lo: Rectangle minimum Y (inclusive)
        x_hi: Rectangle maximum X (inclusive)
        y_hi: Rectangle maximum Y (inclusive)
    
    Returns:
        True if point is within or on rectangle bounds
    """
    return x_lo <= x <= x_hi and y_lo <= y <= y_hi


def ranges_overlap(a_min: int, a_max: int, b_min: int, b_max: int) -> bool:
    """
    Check if two inclusive ranges [a_min, a_max] and [b_min, b_max] overlap.
    
    Two ranges overlap if they share at least one common value. This handles
    all cases including:
    - Complete overlap (one range contains the other)
    - Partial overlap (ranges intersect)
    - Adjacent ranges (touching at boundaries)
    
    Args:
        a_min: First range minimum (inclusive)
        a_max: First range maximum (inclusive)
        b_min: Second range minimum (inclusive)
        b_max: Second range maximum (inclusive)
    
    Returns:
        True if ranges overlap or touch
    
    Examples:
        >>> ranges_overlap(0, 10, 5, 15)   # Partial overlap
        True
        >>> ranges_overlap(0, 10, 11, 20)  # No overlap
        False
        >>> ranges_overlap(0, 10, 10, 20)  # Adjacent/touching
        True
        >>> ranges_overlap(5, 8, 0, 20)    # Complete containment
        True
    """
    return not (a_max < b_min or b_max < a_min)