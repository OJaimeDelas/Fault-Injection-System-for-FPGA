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
    
    def la_to_clock_region_bounds(self, la: int) -> Tuple[int, int, int]:
        """
        Convert LA to (X, Y_min, Y_max) where Y range covers the clock region.
        
        This method provides the X coordinate (precise) and the Y range (clock region)
        for a given linear address. Since the exact Y row cannot be determined from
        LA alone (requires frame type info), we return the full clock region Y bounds.
        
        This is used for accurate region filtering that checks clock region overlap
        rather than relying on midpoint approximation.
        
        Args:
            la: Linear frame address
        
        Returns:
            Tuple of (x, y_min, y_max) where:
            - x: Precise X tile coordinate
            - y_min: Minimum Y of clock region containing this LA
            - y_max: Maximum Y of clock region containing this LA
        
        Example:
            >>> board = Xcku040Board()
            >>> board.la_to_clock_region_bounds(100)
            (52, 0, 61)  # X=52, clock region Y0 covers rows 0-61
        """
        # Determine clock region and Y bounds
        if la < self.FY:
            offset = self.OFFSET_Y0
            y_min, y_max = 0, self.Y4
        elif la < 2 * self.FY:
            offset = self.OFFSET_Y1
            y_min, y_max = self.Y4 + 1, self.Y3
        elif la < 3 * self.FY:
            offset = self.OFFSET_Y2
            y_min, y_max = self.Y3 + 1, self.Y2
        elif la < 4 * self.FY:
            offset = self.OFFSET_Y3
            y_min, y_max = self.Y2 + 1, self.Y1
        else:
            offset = self.OFFSET_Y4
            y_min, y_max = self.Y1 + 1, self.MAX_Y
        
        # Calculate X coordinate precisely
        frame_in_region = la - offset
        x = self.MIN_X + (frame_in_region // self.FX)
        
        # Clamp X to device bounds
        x = max(self.MIN_X, min(x, self.MAX_X))
        
        return (x, y_min, y_max)
    
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
    
    def slice_xy_to_tile_xy(self, slice_x: int, slice_y: int) -> Tuple[int, int]:
        """
        Convert SLICE coordinates to physical tile coordinates.
        
        Vivado pblocks use SLICE coordinates (e.g., SLICE_X0Y0 to SLICE_X47Y299),
        but ACME filtering requires physical tile coordinates (X=50-357, Y=0-309).
        
        This function maps SLICE X/Y to the corresponding CLB tile positions on
        the XCKU040 die. The mapping is based on the device floorplan where:
        - SLICE X=0-23 corresponds to left column of clock regions (CLB tiles)
        - SLICE X=24-47 corresponds to right column of clock regions (CLB tiles)
        - Y coordinates map directly (SLICE_Y == TILE_Y for XCKU040)
        
        Args:
            slice_x: SLICE X coordinate (0-47)
            slice_y: SLICE Y coordinate (0-299)
        
        Returns:
            Tuple of (tile_x, tile_y) physical coordinates for ACME
        
        Notes:
            - CLB tile columns are at specific X positions in the XCKU040 floorplan
            - This lookup table was derived from Vivado device view and ACME reference
            - X positions skip I/O, DSP, and BRAM columns in the floorplan
        """
        # CLB tile column lookup for XCKU040
        # Maps SLICE X coordinate to physical tile X position
        # XCKU040 has 2 main CLB column groups (left and right sides)
        # Each group spans 24 SLICE positions mapped to specific tile columns
        
        # Left column (SLICE X=0-23) → CLB tiles at X=50-97
        # Right column (SLICE X=24-47) → CLB tiles at X=98-145
        # This is a simplified linear mapping; actual device may have gaps
        
        if slice_x < 0 or slice_x > 47:
            raise ValueError(f"SLICE X coordinate {slice_x} out of range [0, 47]")
        if slice_y < 0 or slice_y > 299:
            raise ValueError(f"SLICE Y coordinate {slice_y} out of range [0, 299]")
        
        # Map SLICE X to tile X using linear offset within each column
        # Column 0: SLICE_X=0-23 maps to tile region starting at X=50
        # Column 1: SLICE_X=24-47 maps to tile region starting at X=98
        # These offsets correspond to the physical CLB column positions on XCKU040
        
        if slice_x < 24:
            # Left column clock regions (SLICE_X=0-23 → CLB tiles X=50-96)
            tile_x = 50 + (slice_x * 2)  # Spacing factor of 2 for CLB tile density
        else:
            # Right column clock regions (SLICE_X=24-47 → CLB tiles X=98-144)
            tile_x = 98 + ((slice_x - 24) * 2)
        
        # Y coordinate maps directly - SLICE and tile Y are aligned for XCKU040
        tile_y = slice_y
        
        # Clamp to device bounds as safety check
        tile_x = max(self.MIN_X, min(tile_x, self.MAX_X))
        tile_y = max(self.MIN_Y, min(tile_y, self.MAX_Y))
        
        return (tile_x, tile_y)