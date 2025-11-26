# FI Logging System

Centralized event logging with file and console output, verbosity
levels, and per-category filtering.

## Architecture

### Files

- `events.py`: Core logging functions and infrastructure
- Controlled by `fi_settings.py` configuration
- Setup via `fi/core/campaign/logging_setup.py`

### Verbosity Levels

Set via `LOG_LEVEL` in `fi_settings.py`:

- **minimal**: Only errors and campaign summary
  - Campaign start/end messages
  - Error messages
  - No injection details

- **normal** (default): Major steps
  - Everything in minimal
  - SystemDict loading
  - Board resolution
  - Pool building summary
  - ACME expansions

- **verbose**: Everything
  - Everything in normal
  - Individual injection events
  - Per-module pool breakdowns
  - SEM command details

### Per-Category Toggles

Each event category can be independently enabled/disabled in
`fi_settings.py`:
```python
LOG_SYSTEMDICT = True       # SystemDict loading
LOG_BOARD_RESOLUTION = True # Board resolution
LOG_ACME = True             # ACME expansions
LOG_POOL_BUILDING = True    # Pool building
LOG_INJECTIONS = True       # Individual injections
LOG_SEM_COMMANDS = True     # SEM commands
LOG_ERRORS = True           # Errors (always recommended)
LOG_CAMPAIGN = True         # Campaign start/end
```

### Output Destinations

- **File**: Always written (unless category disabled)
- **Console**: Filtered by LOG_LEVEL
- **Errors**: Always to both file and console

## Usage

### In FI Code

Import and call logging functions:
```python
from fi.log.events import log_systemdict_loaded, log_error

# Log successful operation
system_dict = load_system_dict(path)
log_systemdict_loaded(path, boards, num_modules)

# Log error
try:
    ...
except Exception as e:
    log_error("Failed to do something", exc=e)
```

### Log File Location

Default: `fi/injection_log.txt`

Configure via `fi_settings.py`:
```python
LOG_ROOT = "."  # Directory (relative to fi/)
LOG_FILENAME = "injection_log.txt"  # Filename with extension
```

Or override via CLI (when implemented):
```bash
python -m fi.fault_injection --log-root "custom/path"
```

## Adding New Log Events

To add a new logged event:

1. **Add category toggle** to `fi_settings.py`:
```python
   LOG_MY_FEATURE = True  # My feature events
```

2. **Add function** to `fi/core/logging/events.py`:
```python
   def log_my_event(param1: str, param2: int):
       """Log my event."""
       from fi import fi_settings
       
       if not fi_settings.LOG_MY_FEATURE:
           return
       
       msg = f"[MyFeature] {param1}: {param2}"
       _write_to_file(msg)
       if _should_log_to_console(fi_settings.LOG_MY_FEATURE):
           _write_to_console(msg)
```

3. **Call from code**:
```python
   from fi.log.events import log_my_event
   
   log_my_event("something happened", 42)
```

## Best Practices

1. **Use structured prefixes**: `[SystemDict]`, `[Pool]`, `[ACME]`, etc.
2. **One line per event**: Keep messages concise
3. **Include context**: Module names, counts, paths
4. **Respect verbosity**: High-frequency events (injections) → verbose only
5. **Always log errors**: Even if category disabled

## Log File Format
```
================================================================================
FATORI-V FI Console - Injection Log
Started: 2025-11-20 19:45:23.123456
================================================================================

================================================================================
Campaign Configuration:
  Device: /dev/ttyUSB0 @ 115200 baud
  Area Profile: modules
  Time Profile: uniform
================================================================================
[SystemDict] Loaded from fi/config/system_dict.yaml: 1 boards, 5 modules
[Board] Resolved to 'basys3' (source: default)
[ACME] Expanded CLOCKREGION_X1Y2:CLOCKREGION_X1Y3 → 1250 config bits
[Pool] Built by 'modules': 5000 targets
       By kind: {'CONFIG': 3750, 'REG': 1250}
[Inject] alu/CONFIG: 00001234 → OK
[Inject] alu/REG: reg_id=0 → OK
...

================================================================================
Campaign Complete:
  Total injections: 5000
  Successes: 4998
  Failures: 2
================================================================================
```

## Verbosity Examples

### Minimal Mode
```
Campaign Starting...
[ERROR] Failed to connect to SEM
Campaign Complete: 0 injections (0 successes, 0 failures)
```

### Normal Mode
```
[SystemDict] Loaded from system_dict.yaml: 1 boards, 5 modules
[Board] Resolved to 'basys3' (source: default)
[Pool] Built by 'modules': 5000 targets
       By kind: {'CONFIG': 3750, 'REG': 1250}
Campaign Complete: 5000 injections (4998 successes, 2 failures)
```

### Verbose Mode
```
[SystemDict] Loaded from system_dict.yaml: 1 boards, 5 modules
[Board] Resolved to 'basys3' (source: default)
[ACME] Expanded CLOCKREGION_X1Y2:CLOCKREGION_X1Y3 → 1250 config bits
[Pool] Built by 'modules': 5000 targets
       By kind: {'CONFIG': 3750, 'REG': 1250}
       alu: {'CONFIG': 250, 'REG': 100}
       lsu: {'CONFIG': 500, 'REG': 150}
[Inject] alu/CONFIG: 00001234 → OK
[Inject] alu/REG: reg_id=0 → OK
[Inject] lsu/CONFIG: 00005678 → OK
...
Campaign Complete: 5000 injections (4998 successes, 2 failures)
```