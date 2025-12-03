# FATORI-V FI Console - Logging Guide

## Overview

The FI console uses a simple three-level logging system:
- **minimal**: Only critical information (errors, campaign summary)
- **normal**: Standard operation (lifecycle, system init, pool building)
- **verbose**: Everything (including every injection and SEM command)

## Quick Start

Set the log level via CLI:
```bash
# Minimal mode - only errors and summary
python3 fault_injection.py --log-level minimal --area device

# Normal mode - default, good for most use cases
python3 fault_injection.py --log-level normal --area device

# Verbose mode - see everything happen in real-time
python3 fault_injection.py --log-level verbose --area device
```

Or edit `fi_settings.py` for a permanent change:
```python
LOG_LEVEL = "verbose"  # Change default to verbose
```

## What Gets Logged at Each Level

### MINIMAL - Production Mode

**Console Output:**
- Campaign startup banner
- Campaign completion banner
- Campaign summary statistics
- Errors only

**File Log:**
- Same as console (minimal record)

**Use When:**
- Running production campaigns
- You only care if it worked or failed
- Clean console output is important

### NORMAL - Default Mode

**Console Output:**
- Campaign lifecycle (start/end/summary)
- System initialization (dict loading, board resolution, SEM preflight)
- Pool building results
- ACME expansion details
- Errors

**File Log:**
- Everything from console, PLUS:
- ACME cache hits (performance info)
- Individual injections (one line per injection)
- SEM commands and responses (detailed protocol)

**Use When:**
- Typical development and testing
- You want to see progress but not be overwhelmed
- Need detailed file logs for analysis later

### VERBOSE - Debug Mode

**Console Output:**
- Everything enabled
- Real-time injection activity
- Every SEM command and response
- ACME cache behavior
- All system events

**File Log:**
- Complete record of everything

**Use When:**
- Debugging issues
- Monitoring campaign in detail
- Understanding SEM protocol behavior
- Need to see exactly what's happening

## Customizing Log Levels

Want to change what appears at each level? Edit `fi/config/log_levels.py`:
```python
# Example: Add injection visibility to NORMAL level
NORMAL = [
    # ... existing entries ...
    ('injection', True, True),  # Move from (False, True) to (True, True)
]
```

Each entry is a tuple: `(event_name, to_console, to_file)`

### Available Events

| Event | Description |
|-------|-------------|
| `campaign_header` | Campaign startup banner |
| `campaign_footer` | Campaign completion banner |
| `campaign_summary` | Final statistics |
| `systemdict_load` | System dictionary loaded |
| `board_resolution` | Board name resolved |
| `sem_preflight` | SEM connection test |
| `pool_built` | Target pool built |
| `acme_expansion` | ACME region expanded |
| `acme_cache_hit` | ACME cache hit |
| `injection` | Individual injection |
| `sem_command` | SEM command sent |
| `sem_response` | SEM response received |
| `error` | Error occurred |

### Example Customizations

#### Show Injections in NORMAL Mode
```python
# In fi/config/log_levels.py, NORMAL section:
('injection', True, True),  # Changed from (False, True)
```

#### Hide System Init in VERBOSE Mode
```python
# In fi/config/log_levels.py, VERBOSE section:
('systemdict_load', False, True),  # Changed from (True, True)
('board_resolution', False, True),  # Console off, file on
```

#### Create Custom Level

You can add your own level by editing `log_levels.py`:
```python
# Add after VERBOSE definition:
DEBUG_SEM = [
    ('campaign_header', True, True),
    ('campaign_footer', True, True),
    ('sem_command', True, True),    # Only SEM activity
    ('sem_response', True, True),
    ('error', True, True),
]

# Update get_level_config():
def get_level_config(level: str):
    if level == "minimal":
        return MINIMAL
    elif level == "verbose":
        return VERBOSE
    elif level == "debug_sem":  # NEW
        return DEBUG_SEM
    else:
        return NORMAL
```

Then use: `--log-level debug_sem`

## File vs Console

**Key Principle:** File logs are for analysis, console is for monitoring.

At NORMAL level:
- **High-frequency events** (injections, SEM commands) go to file only
- **Low-frequency events** (system init, pool building) go to both

This keeps console readable while maintaining complete file records.

## Common Scenarios

### Scenario 1: Debugging SEM Communication

Use verbose mode to see every command and response:
```bash
python3 fault_injection.py --log-level verbose --area device
```

Watch the console for SEM protocol details.

### Scenario 2: Production Runs

Use minimal mode for clean output:
```bash
python3 fault_injection.py --log-level minimal --area modules
```

Check log file afterward for complete details.

### Scenario 3: Development/Testing

Use normal mode (default) for balanced output:
```bash
python3 fault_injection.py --area device
```

Console shows progress, file has complete record.

### Scenario 4: Performance Analysis

Edit `log_levels.py` to add ACME cache hits to console in NORMAL:
```python
('acme_cache_hit', True, True),  # Added to NORMAL
```

## Tips

1. **File logs always complete** - even at minimal level, file gets more than console
2. **Start with normal** - good default for most use cases
3. **Use verbose sparingly** - helpful for debugging but very noisy
4. **Customize via log_levels.py** - don't edit every log function, just move events between levels
5. **Console for monitoring, file for analysis** - different purposes

## Troubleshooting

### Too Much Console Output

Try minimal mode: `--log-level minimal`

Or edit `log_levels.py` to move noisy events from console:
```python
('injection', False, True),  # File only
```

### Not Enough Detail

Try verbose mode: `--log-level verbose`

Or edit `log_levels.py` to add specific events to console.

### Want Different Behavior

Copy and customize `fi/config/log_levels.py` - it's designed to be edited!

## Summary

- **Three levels**: minimal, normal, verbose
- **One file to edit**: `fi/config/log_levels.py`
- **Simple tuples**: `(event, to_console, to_file)`
- **File logs always complete**, console can be filtered
- **Default is sane**, customize if needed

Simple, clean, and easy to customize!