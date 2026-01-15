# FI Engine — Core Orchestration

This folder contains the core orchestration logic that ties together
CLI arguments, configuration, logging, SEM setup, profile loading,
and the injection controller.

## Architecture

The engine layer sits between the main script (fault_injection.py) and
the specialized subsystems (targets, profiles, semio, acme). It handles:

- Configuration management (CLI → Config object)
- Logging setup and path resolution
- SEM transport and protocol initialization
- Profile discovery and loading
- Board name resolution
- Resource cleanup

## Files

- `controller.py`: Injection controller (glue between profiles, targets, backends)
- `pool_builder.py`: Builds TargetPool from area profile
- `board_resolution.py`: Board name resolution with fallback chain
- `sync.py`: File-based benchmark synchronization
- `signal_handler.py`: Graceful shutdown on Ctrl+C
- `cleanup.py`: Resource cleanup (close files, serial ports)

## Main Campaign Flow
```
fault_injection.py
  ↓
1. parse_args() → Namespace
2. build_config() → Config
3. setup_logging() → LogContext
4. open_sem() → (transport, protocol)
5. load_system_dict() → SystemDict
6. resolve_board_name() → board_name
7. load_area_profile() → AreaProfile
8. load_time_profile() → TimeProfile
9. area_profile.build_pool() → TargetPool
10. create_injection_controller() → InjectionController
11. time_profile.run(controller) → injections happen
12. cleanup_resources()
```

## Board Resolution

Board name can come from three sources (in priority order):

1. **CLI explicit**: `--board basys3`
2. **Auto-detect**: If SystemDict has only one board, use it
3. **Default fallback**: Use DEFAULT_BOARD_NAME from fi_settings.py

If none of these resolve successfully, an error is raised.

Example:
```python
from fi.engine.board_resolution import resolve_board_name

board_name = resolve_board_name(cfg, system_dict)
```
# Returns resolved board name (guaranteed valid)

## Benchmark Synchronization

The FI system can coordinate with external benchmarks via file-based signaling.

**Mechanism:**
- FI blocks until signal file appears
- Benchmark creates file when ready
- FI checks periodically (hybrid: time-based OR count-based)
- Benchmark removes file when done
- FI detects removal and stops gracefully

**Implementation:**
```python
from fi.core.campaign.sync import BenchmarkSync

sync = BenchmarkSync(
    sync_file_path="/tmp/benchmark_ready",
    check_interval_s=1.0,
    check_every_n=100
)

# Block until benchmark ready
if sync.wait_for_benchmark_ready(timeout_s=60.0):
    # Run campaign
    for target in pool:
        inject(target)
        sync.on_injection()  # Update counter
        
        # Check if benchmark still active
        if sync.should_check():
            if not sync.check_benchmark_active():
                break  # Benchmark stopped
```

**CLI Arguments:**
- `--wait-for-file <path>` - Enable synchronization
- `--check-interval <seconds>` - Time-based check frequency
- `--check-every-n <count>` - Count-based check frequency
- `--sync-timeout <seconds>` - Maximum wait time

**See:** `sync.py` for complete implementation.

## Adding New Engine Helpers

When adding new orchestration logic:

1. Create a focused module (e.g., `xyz_setup.py`)
2. Export a main function with clear signature
3. Document inputs and outputs in docstring
4. Add import and call to fault_injection.py
5. Update this README

Keep engine modules small and focused. Each should handle one aspect
of the setup/teardown flow.

## Configuration

The `Config` dataclass centralizes all campaign configuration:
```python
from fi.engine.config import build_config

cfg = build_config(args)

# Access configuration
print(cfg.dev)           # Serial device
print(cfg.board_name)    # Board name (or None if not specified)
print(cfg.area_profile)  # Area profile name
```

Configuration comes from three sources (in priority order):
1. CLI arguments
2. fi_settings.py defaults
3. Hardcoded fallbacks

## Error Handling

Engine helpers should:
- Raise clear ValueError/FileNotFoundError for configuration problems
- Let exceptions propagate to fault_injection.py (which handles them)
- Document what exceptions they raise in docstrings

The main script (fault_injection.py) catches all exceptions and ensures
cleanup happens via the finally block.

---

## Related Documentation

### Core Systems
- [Main README](../../Readme.md) - System overview
- [Config System](../config/Readme.md) - Campaign configuration
- [Logging System](../logging/Readme.md) - Campaign event logging

### Backends
- [Backend Overview](../../backend/Readme.md) - Injection backends
- [SEM Backend](../../backend/sem/Readme.md) - CONFIG injection
- [Register Injection](../../backend/reg_inject/Readme.md) - REG injection

### Profiles
- [Profile System](../../profiles/Readme.md) - Profile overview
- [Area Profiles](../../profiles/area/Readme) - Build target pools
- [Time Profiles](../../profiles/time/Readme) - Control campaign via controller

### Targets
- [Target System](../../targets/Readme.md) - TargetPool iteration and routing

### See Also
- `fault_injection.py` - Creates and runs controller
- `targets/router.py` - Target routing logic
- Signal handlers for graceful shutdown