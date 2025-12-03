# ACME — Address Computation for Memory Encoding

This folder contains the ACME engine for converting FPGA region
coordinates into specific configuration bit addresses (LFAs) that
the SEM controller understands.

## Philosophy

**ACME is a tool, not a setup step.**

Area profiles call ACME functions directly when they need to expand
region coordinates into addresses. No global engine needs to be created
at startup. ACME engines are created on-demand and discarded after use.

## Public API

Located in `fi/targets/acme_sem_decoder.py`:

```python
from fi.targets.acme_sem_decoder import expand_pblock_to_config_bits

# Convert region coordinates to list of addresses
addresses = expand_pblock_to_config_bits(
    region="CLOCKREGION_X1Y2:CLOCKREGION_X1Y3",  # Legacy format (deprecated)
    board_name="basys3",
    ebd_path="fi/backend/acme/design.ebd"
)
# Returns: ["00001234AB", "00001236CD", ...]
```

**New coordinate-based region specification**:

```python
from fi.backend.acme import make_acme_engine

# Create engine for specific board and EBD
engine = make_acme_engine("xcku040", "build_v1.ebd")

# Filter by physical coordinates
region_spec = {
    'x_lo': 50,  'y_lo': 50,
    'x_hi': 75,  'y_hi': 65
}
addresses = engine.expand_region_to_config_bits(region_spec)

# Or get device-wide addresses
addresses = engine.expand_region_to_config_bits(region_spec=None)
```

For device-wide expansion (legacy API):

```python
from fi.targets.acme_sem_decoder import expand_device_to_config_bits

addresses = expand_device_to_config_bits(
    full_device_region="CLOCKREGION_X0Y0:CLOCKREGION_X3Y3",
    board_name="basys3",
    ebd_path="fi/backend/acme/design.ebd"
)
```

## Architecture

### Internal Components (fi/backend/acme/)

- **Board models**: `basys3.py`, `xcku040.py` - Device-specific parameters and coordinate mapping
- **EBD parser**: `core.py` - Reads essential bits database files
- **ACME engine**: `factory.py` - Implements address computation and region filtering
- **Caching**: `cache.py` - Result caching for performance
- **Geometry**: `geometry.py` - Coordinate mapping utilities

### External Interface (fi/targets/)

- **acme_sem_decoder.py**: Clean API for area profiles
  - Creates engine on-demand
  - Handles errors gracefully
  - Returns addresses as hex strings
  - No global state

## How It Works

### Region Filtering

1. Area profile calls `engine.expand_region_to_config_bits(region_spec)`
2. Engine checks cache for matching (board, EBD, coordinates)
3. On cache miss:
   - Parse EBD file to get all device addresses
   - For each address, unpack LFA to get linear frame address (LA)
   - Map LA to physical (X, Y) coordinates using board-specific equations
   - Filter addresses that fall within region rectangle
   - Cache filtered results
4. Return list of hex address strings
5. Engine can be reused or discarded

### Legacy: Device-Wide Expansion

1. Area profile calls `expand_pblock_to_config_bits()` or `expand_device_to_config_bits()`
2. Function creates ACME engine for specified board
3. Engine loads EBD file and device parameters
4. All addresses extracted without filtering
5. Addresses returned as list of hex strings
6. Engine is discarded (no persistent state)

## Region Specification

ACME supports direct physical coordinate filtering:

```python
# Rectangle defined by tile coordinates
region_spec = {
    'x_lo': 50,   # Minimum X coordinate (inclusive)
    'y_lo': 50,   # Minimum Y coordinate (inclusive)
    'x_hi': 75,   # Maximum X coordinate (inclusive)
    'y_hi': 65    # Maximum Y coordinate (inclusive)
}
```

Coordinates are in physical tiles:
- **XCKU040**: X ∈ [50, 357], Y ∈ [0, 309]
- **Basys3**: X ∈ [0, 209], Y ∈ [0, 159]

For device-wide addresses, pass `region_spec=None`.

## Cache System

### Cache Location

Default: `fi/build/acme/`

### Cache Types

**Device-Wide Cache**:
- Filename: `{board}__{ebd_name}__{size}__{mtime}__{hash}.txt`
- Contains all addresses for the entire device
- Invalidated if EBD file changes (size/mtime/path)

**Region-Specific Cache**:
- Filename: `{board}_{ebd_name}_{x_lo}_{y_lo}_{x_hi}_{y_hi}.txt`
- Contains only addresses within specified rectangle
- Keyed by physical coordinates and EBD filename

### Cache Format

- One 10-character hex address per line
- Uppercase format (e.g., `00001234AB`)
- No headers or comments
- Plain text for easy inspection

### Cache Control

```python
# Disable caching for this call
addresses = engine.expand_region_to_config_bits(
    region_spec=region,
    use_cache=False
)
```

Debug environment variables:
```bash
export FI_ACME_DEBUG=1        # Enable debug output
export FI_ACME_DEBUG_N=10     # Show first 10 LFAs
export FI_ACME_REBUILD=1      # Force cache rebuild
```

## EBD File Naming ⚠️ CRITICAL

**IMPORTANT**: Different FPGA designs **MUST** use different EBD filenames.

The cache system uses the EBD filename as part of the cache key. If two
different implementations both generate files named `design.ebd`, they will
**incorrectly share cache entries** for regions with the same coordinates.

**Recommended naming convention**:
```
design_v1.ebd              # Version-based
design_v2.ebd

project_config1.ebd        # Configuration-based
project_config2.ebd

build_20250126_143000.ebd  # Timestamp-based
build_20250126_150000.ebd
```

**The upper layer (FATORI-V build system) is responsible for ensuring unique
EBD filenames.** The FI system treats files with the same name as identical.

### Why This Matters

Given the same coordinates (50, 50, 75, 65):
- Design A with `design.ebd` → generates cache
- Design B with `design.ebd` → **reuses Design A's cache** (WRONG!)

Result: Design B injects into Design A's addresses, causing unpredictable behavior.

### Solution

Ensure each design generates a unique EBD filename before running fault injection.

## Coordinate Mapping

### Physical Tile Coordinates

- Origin: (0, 0) at device corner
- Units: Tiles (configurable logic blocks)
- Used for region specification and filtering

### Linear Frame Address (LA)

- Extracted from 40-bit LFA: LA = LFA[39:12]
- Maps to physical frames in FPGA configuration memory
- Converted to (X, Y) coordinates for filtering

### Board-Specific Mapping

**XCKU040 (UltraScale)**:
- Uses ACME reference equations from IEEE Access 2019 paper
- Frame address: `LA = SLOPE × X + OFFSET(Y_region)`
- SLOPE = 17, OFFSET varies by clock region
- 5 clock regions (Y0-Y4) with boundaries at Y=61, 123, 185, 247

**Basys3 (XC7A35T)**:
- Simplified model for 7-Series architecture
- Approximate tile-level granularity
- Conservative filtering (may include extra tiles)

## Adding Support for New Boards

To add a new FPGA device:

1. **Create board model** in `fi/backend/acme/` (e.g., `zynq7.py`):

```python
class Zynq7Board:
    """Device map for Zynq-7000."""
    
    FAMILY = "7series"
    WF = 101
    MIN_X = 0
    MAX_X = 150
    MIN_Y = 0
    MAX_Y = 100
    
    def full_device_rect(self):
        return (self.MIN_X, self.MIN_Y, self.MAX_X, self.MAX_Y)
    
    def la_to_xy(self, la: int):
        """Convert linear address to physical coordinates."""
        # Implement device-specific mapping
        ...
    
    def xy_to_la_range(self, x: int, y: int):
        """Convert coordinates to LA range."""
        # Implement inverse mapping
        ...
```

2. **Register in `fi/backend/acme/factory.py`**:

```python
def load_board(name: str):
    key = name.lower()
    if key in ("zynq7", "zynq-7000"):
        return Zynq7Board()
    # ... existing boards
```

3. **Add board entry to system_dict.yaml**:

```yaml
zynq7:
  device:
    min_x: 0
    max_x: 150
    min_y: 0
    max_y: 100
    wf: 101
  targets:
    module1:
      x_lo: 10
      y_lo: 10
      x_hi: 30
      y_hi: 30
      registers: [1, 2, 3]
```

4. **Provide EBD file** for the device (essential bits database)

## Performance Notes

### Initial Generation (no cache)

- **XCKU040 device-wide**: ~2-5 minutes
- **Region filtering**: ~3-10 minutes (depends on device/region size)
- **Basys3 device-wide**: ~1-3 minutes

### Cached Runs

- **Read time**: <1 second
- **Memory**: ~10-50 MB depending on region size

### Cache Size

- **Device-wide**: ~5-20 MB per cache file
- **Region-specific**: ~100 KB - 5 MB per region
- **Typical campaign** (10 targets): ~50-100 MB total cache

Consider:

- **Caching**: Enabled by default, dramatically speeds up subsequent runs
- **Sampling**: Device profile supports `sample_size` argument for testing
- **Filtering**: Use specific regions instead of device-wide when possible

## Troubleshooting

### Empty address list returned

**Symptoms**: `expand_region_to_config_bits()` returns `[]`

**Possible causes**:
- Region coordinates outside device bounds
- EBD file parsing failure
- Cache file corrupted

**Solutions**:
1. Verify coordinates within device bounds (see board model)
2. Check EBD file exists and is readable
3. Clear cache: `rm -rf fi/build/acme/*`
4. Check logs for error details
5. Enable debug: `export FI_ACME_DEBUG=1`

### Wrong addresses generated

**Symptoms**: Fault injection targets wrong regions

**Possible causes**:
- Incorrect coordinates in system_dict.yaml
- Board name mismatch
- **EBD file reused from different design** (cache collision)

**Solutions**:
1. Verify region coordinates match Vivado implementation
2. Check board name matches device (xcku040 vs basys3)
3. **Ensure unique EBD filename for each design**
4. Clear cache and regenerate

### Cache not used (slow regeneration every run)

**Symptoms**: ACME takes minutes even with valid cache

**Possible causes**:
- EBD file modified (mtime/size changed)
- Coordinates changed slightly
- Cache disabled

**Solutions**:
1. Ensure EBD file stable between runs
2. Use consistent coordinates in system_dict.yaml
3. Check `use_cache=True` in API calls
4. Verify cache directory writable

### Slow expansion (even with cache)

**Symptoms**: Region filtering takes >30 seconds

**Possible causes**:
- Large region (many addresses to filter)
- Cache misses due to coordinate changes
- Debug mode enabled

**Solutions**:
1. Use smaller regions when possible
2. Ensure stable coordinates for cache hits
3. Disable debug: `unset FI_ACME_DEBUG`
4. Consider device-wide cache if filtering multiple nearby regions

### Cache directory growing large

**Symptoms**: `fi/build/acme/` consuming disk space

**Solutions**:
```bash
# List cache files with sizes
ls -lh fi/build/acme/

# Remove old caches (device-wide)
rm fi/build/acme/*__design__*.txt

# Remove region caches for specific coordinates
rm fi/build/acme/*_50_50_75_65.txt

# Clear all cache
rm -rf fi/build/acme/*
```

## Error Handling

ACME functions handle errors gracefully:

```python
addresses = expand_pblock_to_config_bits(region, board, ebd)

if not addresses:
    # Check logs for error details
    logger.warning(f"No addresses for region {region}")
    # Campaign can continue with empty address set
    # or fall back to device-wide expansion
```

Internal errors are logged but don't crash the system.

## No Setup Required

Unlike previous designs, ACME does not require:
- Pre-initialization at startup
- Global engine instances
- Setup functions in fi/core/campaign/

Just call the expansion functions when needed. Each call is independent.

Engines can be reused if needed:
```python
# Reuse engine for multiple regions (efficient)
engine = make_acme_engine("xcku040", "design.ebd")
addr1 = engine.expand_region_to_config_bits(region1)
addr2 = engine.expand_region_to_config_bits(region2)
addr3 = engine.expand_region_to_config_bits(region3)
```

Or create fresh each time (simpler):
```python
# Create new engine each time (also fine)
addr1 = make_acme_engine("xcku040", "design.ebd").expand_region_to_config_bits(region1)
addr2 = make_acme_engine("xcku040", "design.ebd").expand_region_to_config_bits(region2)
```

Both approaches work; the first is slightly more efficient if making many calls.

## References

- **ACME Paper**: IEEE Access 2019, "ACME: A Tool to Improve Configuration Memory Fault Injection in SRAM-Based FPGAs"
- **Vivado UG470**: 7 Series FPGAs Configuration User Guide
- **Vivado UG570**: UltraScale Architecture Configuration User Guide
