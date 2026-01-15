# FI Configuration System

Centralized configuration management for the FI engine, combining default settings from `fi_settings.py` with CLI argument overrides.

## Overview

The configuration system provides:
- **Config dataclass**: Single source of truth for runtime settings
- **CLI parser**: Comprehensive argument parsing with validation
- **Seed manager**: Reproducible randomness for campaigns
- **Path resolver**: Intelligent path resolution relative to fi/ directory

## Architecture
```
fi_settings.py (defaults)
     ↓
cli_parser.py (parse CLI args)
     ↓
config.py (merge into Config dataclass)
     ↓
seed_manager.py (derive seeds if needed)
     ↓
Config object → Used by all engine modules
```

## Files

- **config.py**: Config dataclass definition (dumb data container)
- **cli_parser.py**: Argument parser with validation and help text
- **seed_manager.py**: Seed generation and derivation for reproducibility
- **path_resolver.py**: Path resolution utilities relative to fi/ directory

---

## Config Dataclass

The `Config` dataclass in `config.py` is a simple data container with no logic. Every setting from `fi_settings.py` can be overridden via CLI.

### Major Setting Categories

**Serial/SEM:**
- `dev`: Serial device (default: `/dev/ttyUSB0`)
- `baud`: Baud rate (default: 1250000)
- `sem_clock_hz`: SEM clock frequency
- `sem_preflight_required`: Whether to require SEM preflight test

**Profiles:**
- `area_profile`: Area profile name (e.g., "device", "modules")
- `area_args`: Opaque args string passed to area profile
- `time_profile`: Time profile name (e.g., "uniform", "poisson")
- `time_args`: Opaque args string passed to time profile

**File Inputs:**
- `system_dict_path`: Path to system dictionary YAML
- `ebd_path`: Path to Essential Bits Data (.ebd) file  
- `pool_file_path`: Optional pre-built target pool YAML

**Logging:**
- `log_root_override`: Override log directory location
- `log_level`: Console verbosity ("minimal", "normal", "verbose")
- Individual event toggles: `log_systemdict`, `log_acme`, etc.

**Register Injection:**
- `reg_inject_force_disabled`: Disable even if REG targets exist
- `reg_inject_idle_id`: Idle register ID value
- `reg_inject_reg_id_width`: Register ID bit width

**Seeds (Reproducibility):**
- `global_seed`: Master seed for entire campaign
- `area_seed`: Explicit seed for area profile (overrides derivation)
- `time_seed`: Explicit seed for time profile (overrides derivation)
- `global_seed_was_generated`: Tracks if global_seed was auto-generated

**Target Pool Export:**
- `tpool_auto_save`: Automatically export generated pools
- `tpool_output_dir`: Directory for pool YAML files
- `tpool_output_name`: Custom name for exported pool

**Debug:**
- `debug`: Enable debug mode (stub hardware, test pool building)

---

## CLI Parser

The `cli_parser.py` module creates a comprehensive argument parser using argparse.

### Major Argument Groups

**Core Options:**
```bash
-d/--dev DEV              Serial device
-b/--baud BAUD            Baud rate
--area PROFILE            Area profile name
--area-args ARGS          Area profile arguments
--time PROFILE            Time profile name  
--time-args ARGS          Time profile arguments
```

**System Inputs:**
```bash
--system-dict PATH        System dictionary YAML
--ebd PATH                Essential bits data file
--board NAME              Board name (e.g., "xcku040")
```

**Logging:**
```bash
--log-root DIR            Log directory base
--log-level LEVEL         Console verbosity (minimal/normal/verbose)
--log-systemdict          Enable/disable systemdict logging
--log-acme-expansion      Enable/disable ACME logging
--log-injections          Enable/disable injection logging
# ... (individual event toggles)
```

**Register Injection:**
```bash
--reg-inject-disabled           Disable register injection
--reg-inject-idle-id ID         Idle register ID
--reg-inject-reg-id-width BITS  Register ID bit width
```

**Seeds:**
```bash
--global-seed SEED        Master seed for campaign
--area-seed SEED          Explicit area profile seed
--time-seed SEED          Explicit time profile seed
```

**Target Pool:**
```bash
--tpool-name NAME               Custom pool export name
--tpool-output PATH             Explicit pool export path
--tpool-output-dir DIR          Pool export directory
--no-tpool-save                 Disable automatic pool export
--tpool-size-break-repeat-only  Control pool size behavior
--tpool-absolute-cap N          Hard cap on pool size
```

**Debug:**
```bash
--debug                   Enable debug mode (no hardware)
```

### CLI Override Priority

Settings are resolved in this order (highest priority first):
1. CLI arguments (e.g., `--baud 115200`)
2. Environment variables (if implemented)
3. `fi_settings.py` defaults

---

## Seed Management System

The `seed_manager.py` module provides reproducible randomness for campaigns.

### Seed Hierarchy
```
global_seed (master)
  ├─→ area_seed (derived or explicit)
  └─→ time_seed (derived or explicit)
```

### Automatic Seed Generation

If no `--global-seed` is provided:
```python
global_seed = generate_global_seed()
# Combines time + random for uniqueness
```

The generated seed is displayed in campaign output and can be used to reproduce the campaign:
```bash
# First run (seed auto-generated)
python -m fi.fault_injection --area device
# Output: "Using auto-generated global_seed: 1234567890"

# Reproduce exact campaign
python -m fi.fault_injection --area device --global-seed 1234567890
```

### Seed Derivation

If `--global-seed` is provided but not `--area-seed` or `--time-seed`:
```python
area_seed = hash(("area", global_seed)) % (2**32)
time_seed = hash(("time", global_seed)) % (2**32)
```

This ensures:
- Area and time profiles get different seeds
- Derivation is deterministic (same global_seed → same derived seeds)
- Each profile controls its own random behavior

### Explicit Seed Override

You can override derived seeds:
```bash
# Use global seed for area, but custom seed for time
python -m fi.fault_injection \
    --global-seed 12345 \
    --time-seed 99999
```

### Reproducibility Guarantees

**Reproducible** (same results every time):
- Same `--global-seed` → Same target selection and injection timing
- Same profile args + seed → Same behavior

**Not guaranteed reproducible**:
- No seed specified (uses auto-generated seed)
- External factors (benchmark synchronization, file system changes)

---

## Path Resolution

The `path_resolver.py` module handles relative path resolution.

### Path Resolution Rules

Relative paths in CLI arguments are resolved relative to:
1. Current working directory (CWD) for most paths
2. `fi/` directory for internal defaults

Example:
```bash
# Relative to CWD
--system-dict my_configs/system.yaml
# → Resolves to: $(pwd)/my_configs/system.yaml

# Absolute path (unchanged)
--system-dict /home/user/configs/system.yaml
# → Resolves to: /home/user/configs/system.yaml
```

### Default Path Behavior

Paths from `fi_settings.py` are resolved relative to the `fi/` directory:
```python
# In fi_settings.py
SYSTEM_DICT_PATH = "core/config/system_dict.yaml"
# → Resolves to: /path/to/fi/core/config/system_dict.yaml
```

This allows the FI engine to find its default files regardless of where it's invoked from.

---

## Usage Examples

### Minimal (All Defaults)
```bash
python -m fi.fault_injection
```
Uses all settings from `fi_settings.py`.

### Override Key Settings
```bash
python -m fi.fault_injection \
    --dev /dev/ttyUSB1 \
    --baud 115200 \
    --area modules \
    --area-args "pool_size=500,ratio=0.3"
```

### Reproducible Campaign
```bash
# Run with specific seed
python -m fi.fault_injection \
    --global-seed 42 \
    --area device \
    --time uniform \
    --time-args "rate_hz=10"
```

### Debug Mode (No Hardware)
```bash
python -m fi.fault_injection \
    --debug \
    --area modules \
    --area-args "pool_size=100"
```
Tests pool building and campaign flow without requiring hardware.

### Custom Paths
```bash
python -m fi.fault_injection \
    --system-dict /path/to/custom_dict.yaml \
    --ebd /path/to/design.ebd \
    --log-root /path/to/results
```

---

## Integration with Other Modules

### Engine Modules
All engine modules receive the `Config` object:
```python
def run_campaign(cfg: Config):
    # Access any setting
    print(f"Device: {cfg.dev} @ {cfg.baud} baud")
    print(f"Area: {cfg.area_profile}")
    print(f"Global seed: {cfg.global_seed}")
```

### Profile Loaders
Profiles receive `global_seed` automatically:
```python
def make_profile(args, *, global_seed, settings):
    # Area/time profiles get derived seeds if not explicitly provided
    return MyProfile(args, global_seed)
```

### Logging System
Log level controls event visibility:
```python
# In logging code
if cfg.log_level == "verbose":
    log_injection_details()
```

---

## Best Practices

1. **Use global_seed for reproducibility**: Always specify `--global-seed` for campaigns you want to reproduce
2. **Don't edit fi_settings.py for campaigns**: Use CLI args instead to avoid git conflicts
3. **Save seeds from runs**: Campaign output includes the seed used
4. **Use debug mode for testing**: `--debug` validates pool building without hardware
5. **Override individual settings**: No need to specify all settings, just the ones you want to change

---

## Related Documentation

### Core Systems
- [Main README](../../Readme.md) - System overview, CLI reference section
- [Logging System](../logging/Readme.md) - Log configuration settings
- [Campaign Controller](../campaign/Readme.md) - Uses Config for campaign execution

### Backends
- [Backend Overview](../../backend/Readme.md) - Backend configuration
- [SEM Backend](../../backend/sem/Readme.md) - SEM configuration settings
- [Register Injection](../../backend/reg_inject/Readme.md) - Register injection settings

### Profiles
- [Profile System](../../profiles/Readme.md) - Profile configuration
- [Area Profiles](../../profiles/area/Readme) - Area profile arguments
- [Time Profiles](../../profiles/time/Readme) - Time profile arguments

### See Also
- `fi_settings.py` - Default configuration values (source of truth)
- `fault_injection.py` - Config instantiation and usage
- CLI help: `python -m fi.fault_injection --help`
- Seed management examples in main README