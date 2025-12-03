# =============================================================================
# FATORI-V • FI ACME Board Config
# File: fi/backend/acme/xcku040.py
# -----------------------------------------------------------------------------
# Board/device map for XCKU040 (UltraScale) — used by KCU105 and AES-KU040.
#=============================================================================

from __future__ import annotations
from typing import Tuple


class Xcku040Board:
    """
    Device map for the XCKU040 die used on KCU105 and AES-KU040 boards.
    
    Provides device-level constants and coordinate mapping functions for
    the ACME address generation and filtering system.
    
    Physical Layout (from ACME reference implementation):
    - Device tile bounds: X=[50, 357], Y=[0, 309]
    - Clock region rows (Y boundaries): Y4=61, Y3=123, Y2=185, Y1=247
    - Frames per tile column (FX): 17
    - Frames per clock region row (FY): 5236
    - Words per frame (WF): 123
    
    Attributes
    ----------
    FAMILY : str
        Device family label.
    WF : int
        Words per configuration frame (UltraScale: 123).
    DUMMY : int
        Header/dummy line count in certain EBD layouts.
    MIN_X, MAX_X, MIN_Y, MAX_Y : int
        Physical tile extents (inclusive).
    FX : int
        Frames per tile column (for coordinate mapping).
    FY : int
        Frames per clock region row (for coordinate mapping).
    """
    
    FAMILY = "ultrascale"
    WF = 123
    DUMMY = 141
    
    # Physical tile extents (from ACME mainHeader.h)
    MIN_X = 50
    MAX_X = 357
    MIN_Y = 0
    MAX_Y = 309
    
    # Frame geometry parameters (from ACME mainHeader.h)
    FX = 17      # Frames per X coordinate (tile column)
    FY = 5236    # Frames per horizontal clock region
    
    # Clock region Y boundaries (from ACME mainHeader.h)
    # These define the row boundaries for each clock region pair
    Y4 = 61      # Maximum Y of clock region Y4 (bottom)
    Y3 = 123     # Maximum Y of clock region Y3
    Y2 = 185     # Maximum Y of clock region Y2
    Y1 = 247     # Maximum Y of clock region Y1 (top)
    
    # Frame address offsets per clock region (from ACME pBlockRange.cpp)
    # These are the intercepts in the linear equation: Frame = SLOPE * X + OFFSET
    # The slope is always FX (17), the offset varies by clock region pair
    OFFSET_Y0 = 0           # Clock regions 17-20 (Y: 0-61)
    OFFSET_Y1 = 10472       # Clock regions 13-16 (Y: 62-123)
    OFFSET_Y2 = 20944       # Clock regions 9-12  (Y: 124-185)
    OFFSET_Y3 = 31416       # Clock regions 5-8   (Y: 186-247)
    OFFSET_Y4 = 41888       # Clock regions 1-4   (Y: 248-309)
    
    def full_device_rect(self) -> Tuple[int, int, int, int]:
        """
        Return the (x_lo, y_lo, x_hi, y_hi) rectangle covering the whole device.
        
        Returns:
            Tuple of (min_x, min_y, max_x, max_y)
        """
        return (self.MIN_X, self.MIN_Y, self.MAX_X, self.MAX_Y)
    
    def la_to_xy(self, la: int) -> Tuple[int, int]:
        """
        Convert linear frame address (LA) to physical tile coordinates (X, Y).
        
        Uses the reverse ACME equations derived from the reference implementation.
        The forward equation is: LA = SLOPE * X + OFFSET, where SLOPE = FX.
        
        Algorithm:
        1. Determine which clock region pair the LA belongs to based on offsets
        2. Calculate X = (LA - OFFSET) / FX
        3. Y is determined by which clock region pair we're in
        
        Args:
            la: Linear frame address (from unpacked LFA)
        
        Returns:
            Tuple of (x, y) physical tile coordinates
        
        Note:
            This is an approximate mapping. The actual mapping depends on the
            specific frame type and minor address bits, but for filtering
            purposes this tile-level granularity is sufficient.
        """
        # Determine clock region pair and offset based on LA value
        # Clock regions are numbered 1-20, paired as (1-4, 5-8, 9-12, 13-16, 17-20)
        # Each pair covers a range of Y coordinates
        
        if la < self.FY:
            # Clock regions 17-20 (Y: 0 to Y4=61)
            offset = self.OFFSET_Y0
            y_base = 0
            y_range = self.Y4
        elif la < 2 * self.FY:
            # Clock regions 13-16 (Y: Y4+1=62 to Y3=123)
            offset = self.OFFSET_Y1
            y_base = self.Y4 + 1
            y_range = self.Y3
        elif la < 3 * self.FY:
            # Clock regions 9-12 (Y: Y3+1=124 to Y2=185)
            offset = self.OFFSET_Y2
            y_base = self.Y3 + 1
            y_range = self.Y2
        elif la < 4 * self.FY:
            # Clock regions 5-8 (Y: Y2+1=186 to Y1=247)
            offset = self.OFFSET_Y3
            y_base = self.Y2 + 1
            y_range = self.Y1
        else:
            # Clock regions 1-4 (Y: Y1+1=248 to MAX_Y=309)
            offset = self.OFFSET_Y4
            y_base = self.Y1 + 1
            y_range = self.MAX_Y
        
        # Calculate X coordinate from linear equation: LA = FX * X + offset
        # Therefore: X = (LA - offset) / FX
        frame_in_region = la - offset
        x = self.MIN_X + (frame_in_region // self.FX)
        
        # Y coordinate is approximate - we know the clock region pair,
        # but exact Y within that pair requires more detailed frame type info.
        # For filtering purposes, use the midpoint of the clock region range.
        y = (y_base + y_range) // 2
        
        # Clamp to device bounds
        x = max(self.MIN_X, min(x, self.MAX_X))
        y = max(self.MIN_Y, min(y, self.MAX_Y))
        
        return (x, y)
    
    def xy_to_la_range(self, x: int, y: int) -> Tuple[int, int]:
        """
        Convert physical tile coordinates to linear frame address range.
        
        Returns the range of LA values that could correspond to the given
        tile coordinate. This is the forward direction of la_to_xy().
        
        Args:
            x: Physical X coordinate (tile column)
            y: Physical Y coordinate (tile row)
        
        Returns:
            Tuple of (la_min, la_max) for this tile
        """
        # Determine clock region pair offset based on Y coordinate
        if y <= self.Y4:
            offset = self.OFFSET_Y0
        elif y <= self.Y3:
            offset = self.OFFSET_Y1
        elif y <= self.Y2:
            offset = self.OFFSET_Y2
        elif y <= self.Y1:
            offset = self.OFFSET_Y3
        else:
            offset = self.OFFSET_Y4
        
        # Calculate LA range for this X coordinate
        # Each tile column spans FX frames
        x_offset = x - self.MIN_X
        la_min = offset + (x_offset * self.FX)
        la_max = la_min + self.FX - 1
        
        return (la_min, la_max)