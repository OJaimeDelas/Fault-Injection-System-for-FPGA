# =============================================================================
# FATORI-V • FI ACME Board Config
# File: fi/backend/acme/basys3.py
# -----------------------------------------------------------------------------
# Board/device map for Basys3 (Artix-7, XC7A35T).
#=============================================================================

from __future__ import annotations
from typing import Tuple


class Basys3Board:
    """
    Device map for the Artix-7 XC7A35T used on the Basys3 board.
    
    Provides device-level constants and coordinate mapping functions for
    the ACME address generation and filtering system.
    
    Physical Layout (Artix-7 XC7A35T):
    - Device tile bounds: X=[0, 209], Y=[0, 159]
    - Words per frame (WF): 101
    - Clock regions: 6x6 grid (approximate)
    
    Attributes
    ----------
    FAMILY : str
        Device family label.
    WF : int
        Words per configuration frame (7-Series: 101).
    DUMMY : int
        Header/dummy line count in certain EBD layouts.
    MIN_X, MAX_X, MIN_Y, MAX_Y : int
        Physical tile extents (inclusive).
    """
    
    FAMILY = "7series"
    WF = 101
    DUMMY = 109
    
    # Physical tile extents (inclusive)
    MIN_X = 0
    MAX_X = 209
    MIN_Y = 0
    MAX_Y = 159
    
    # Frame geometry parameters (estimated for XC7A35T)
    # 7-Series uses a different frame addressing scheme than UltraScale
    # These are approximate values for coordinate mapping
    FX = 22      # Approximate frames per tile column (varies by column type)
    FY = 3520    # Approximate frames per clock region row
    
    # Clock region Y boundaries (approximate for 6 rows)
    # Basys3 has fewer clock regions than KCU105
    Y5 = 26      # Bottom clock region boundary
    Y4 = 53
    Y3 = 79
    Y2 = 106
    Y1 = 132
    
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
        
        This is a simplified mapping for Artix-7. The actual 7-Series frame
        addressing is more complex than UltraScale, with different frame types
        and addressing schemes. For filtering purposes, we use an approximate
        tile-level mapping.
        
        Args:
            la: Linear frame address (from unpacked LFA)
        
        Returns:
            Tuple of (x, y) physical tile coordinates
        
        Note:
            This is an approximate mapping suitable for pblock-level filtering.
            More precise mappings would require detailed 7-Series frame documentation.
        """
        # Determine approximate clock region based on LA value
        # 7-Series frame addressing is complex, so we use a simplified model
        
        # Estimate which horizontal region band we're in
        region_row = (la // self.FY) % 6  # 6 clock region rows
        
        # Estimate X coordinate within the region
        frame_in_region = la % self.FY
        x = self.MIN_X + ((frame_in_region * self.MAX_X) // self.FY)
        
        # Map region row to Y coordinate range
        if region_row == 0:
            y = (self.MIN_Y + self.Y5) // 2
        elif region_row == 1:
            y = (self.Y5 + 1 + self.Y4) // 2
        elif region_row == 2:
            y = (self.Y4 + 1 + self.Y3) // 2
        elif region_row == 3:
            y = (self.Y3 + 1 + self.Y2) // 2
        elif region_row == 4:
            y = (self.Y2 + 1 + self.Y1) // 2
        else:
            y = (self.Y1 + 1 + self.MAX_Y) // 2
        
        # Clamp to device bounds
        x = max(self.MIN_X, min(x, self.MAX_X))
        y = max(self.MIN_Y, min(y, self.MAX_Y))
        
        return (x, y)
    
    def xy_to_la_range(self, x: int, y: int) -> Tuple[int, int]:
        """
        Convert physical tile coordinates to linear frame address range.
        
        Returns an approximate range of LA values for the given tile.
        This is less precise than UltraScale due to the more complex
        7-Series frame addressing scheme.
        
        Args:
            x: Physical X coordinate (tile column)
            y: Physical Y coordinate (tile row)
        
        Returns:
            Tuple of (la_min, la_max) for this tile (approximate)
        """
        # Determine which clock region row based on Y
        if y <= self.Y5:
            region_row = 0
        elif y <= self.Y4:
            region_row = 1
        elif y <= self.Y3:
            region_row = 2
        elif y <= self.Y2:
            region_row = 3
        elif y <= self.Y1:
            region_row = 4
        else:
            region_row = 5
        
        # Estimate LA range for this region and X coordinate
        region_base = region_row * self.FY
        x_fraction = x / float(self.MAX_X)
        la_base = region_base + int(x_fraction * self.FY)
        
        # Conservative range - include neighboring frames
        la_min = max(0, la_base - self.FX)
        la_max = la_base + self.FX
        
        return (la_min, la_max)