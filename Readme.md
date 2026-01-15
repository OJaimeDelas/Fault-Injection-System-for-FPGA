# FATORI-V — Fault Injection (FI) Engine

Controls AMD/Xilinx **SEM IP** over UART. Campaigns are defined by:

- a **system dictionary** and optional **injection pool** (WHAT can be injected),
- an **area profile** (WHERE to inject within that space),
- a **time profile** (WHEN to inject),

and are executed through a unified **target** abstraction. The engine can run on its own or be driven by FATORI‑V, and produces deterministic, human‑readable per‑session logs.

---

## Folder overview
```text
fi/
  Readme.md                 # This file
  fi_settings.py            # Engine defaults (serial, SEM, logging, seeds, etc.)
  fault_injection.py        # Main entry point for campaigns

  backend/                  # Hardware/injection backends
    acme/                   # ACME integration for address expansion
      Readme.md             # ACME documentation
      factory.py            # ACME decoder factory
      core.py               # Core ACME functionality
      cache.py              # ACME caching system
      decoder.py            # Address decoder base
      basys3.py             # Basys3-specific decoder
      xcku040.py            # KU040-specific decoder
      geometry.py           # Geometric utilities
    
    sem/                    # SEM IP communication
      Readme.md             # SEM backend documentation
      transport.py          # UART I/O, background RX reader, CR/LF framing
      protocol.py           # SEM command layer (sync, modes, status, inject)
      setup.py              # SEM connection and preflight
    
    reg_inject/             # Register injection via UART fi_coms
      board_interface.py    # Board interface abstraction (UART-based)
      reg_decoder.py        # Register target injection helper
    
    common/                 # Shared backend utilities
      serial_stub.py        # Mock serial for debug mode

  core/                     # Core engine functionality
    campaign/               # Campaign execution
      Readme.md             # Campaign controller documentation
      controller.py         # Injection controller (glue: profiles + targets + backends)
      pool_builder.py       # TargetPool construction from area profiles
      board_resolution.py   # Board name resolution logic
      sync.py               # Benchmark synchronization
      signal_handler.py     # Graceful shutdown (Ctrl+C)
      cleanup.py            # Campaign cleanup
    
    config/                 # Configuration management
      Readme.md             # Config system documentation
      config.py             # Config dataclass (runtime settings container)
      cli_parser.py         # CLI argument parser
      seed_manager.py       # Seed generation and derivation
      path_resolver.py      # Path resolution utilities
      system_dict.yaml      # Default system dictionary
    
    logging/                # Logging system
      Readme.md             # Logging documentation
      events.py             # Log event functions
      message_formats.py    # Log message formatting
      log_levels.py         # Verbosity level definitions
      setup.py              # Log file initialization

  profiles/                 # Area and time profiles
    Readme.md               # Profile system overview
    
    area/                   # Area profiles (WHERE to inject)
      Readme                # Area profile documentation
      base.py               # Base class for area profiles (build_pool API)
      device.py             # Whole-device injection (random sampling)
      modules.py            # Module-scoped injection (targets specific modules)
      target_list.py        # Load explicit target list from YAML
      input.py              # Load external custom area profile
      common/               # Shared area profile utilities
        loader.py           # Dynamic area profile loader
        ratio_selector.py   # CONFIG/REG ratio enforcement
    
    time/                   # Time profiles (WHEN to inject)
      Readme                # Time profile documentation
      base.py               # Base class for time profiles (run(controller) API)
      uniform.py            # Constant injection rate
      ramp.py               # Rate ramp from start_hz to end_hz
      poisson.py            # Exponential inter-arrival times
      microburst.py         # Bursts of N shots separated by gaps
      mmpp2.py              # 2-state Markov-modulated Poisson
      trace.py              # Replay schedule from trace file
      input.py              # Load external custom time profile
      common/               # Shared time profile utilities
        loader.py           # Dynamic time profile loader

  targets/                  # Target abstraction and pools
    Readme.md               # Target system documentation
    types.py                # TargetSpec and TargetKind definitions
    pool.py                 # TargetPool container (ordered list of targets)
    pool_loader.py          # Load explicit target pools from YAML
    pool_writer.py          # Export target pools to YAML
    router.py               # Route targets to backends (CONFIG → SEM, REG → UART)
    dict_loader.py          # System dictionary loader

  console/                  # Interactive SEM console
    Readme.md               # Console documentation
    sem_console.py          # Interactive console (manual/driven modes)
    console_settings.py     # Console configuration
    console_styling.py      # Colors and formatting
    printing.py             # Console output utilities
```

---

## Conceptual model

### Targets and pools

The engine never works directly with "raw addresses" or "register IDs" in its core logic. Instead it uses **TargetSpec** objects defined in `fi/targets/types.py`.

A `TargetSpec` describes **what** to inject:

- `kind` identifies the target type (only 2 valid values):
  - `TargetKind.CONFIG` — Configuration bit injection via SEM
  - `TargetKind.REG` — Register injection via UART fi_coms protocol
- Required fields:
  - `module_name` — Which module this target belongs to (for logging/stats)
- Fields for CONFIG targets:
  - `config_address` — LFA address string (required)
  - `pblock_name` — Pblock name (optional)
- Fields for REG targets:
  - `reg_id` — Register identifier (required)
  - `reg_name` — Human-readable register name (optional)
- Metadata fields:
  - `source` — Where this target came from (e.g., "profile:modules", "pool:file")
  - `tags` — Tuple of strings for filtering/grouping

A collection of targets is stored in a **TargetPool** (`fi/targets/pool.py`):

- `add()` / `add_many()` to build the pool
- `pop_next()` for iteration (returns None when exhausted)
- `reset()` to restart iteration
- `count_by_kind()` / `count_by_module()` for statistics
- `get_stats()` for comprehensive pool information

Area profiles build pools via the `build_pool()` method, which returns a complete TargetPool ready for injection.

---

### System dictionary

Hardware description is centralized in a **system dictionary** loaded by `fi/targets/dict_loader.py`. The dictionary is a YAML file with a per-board structure.

**Actual format** (from `core/config/system_dict.yaml`):
```yaml
xcku040:  # Board name as top-level key
  # Device geometry for ACME address expansion
  device:
    min_x: 0
    max_x: 358
    min_y: 0
    max_y: 310
    wf: 123  # Words per frame
  
  # Injection targets (modules with spatial coordinates)
  targets:
    controller:
      x_lo: 50
      y_lo: 50
      x_hi: 75
      y_hi: 65
      registers: [7, 8, 9, 10, 11, 12]  # reg_ids in this module
      module: ibex_controller
    
    lsu:
      x_lo: 100
      y_lo: 50
      x_hi: 120
      y_hi: 60
      registers: [128, 129, 130, 131]
      module: ibex_load_store_unit
  
  # Complete register index
  registers:
    1: {name: "minor_cnt_o", module: "fatori_fault_mgr"}
    7: {name: "mem_resp_intg_err_irq_pending_q", module: "ibex_controller"}
    128: {name: "addr_incr_req_i", module: "ibex_load_store_unit"}
    # ... (complete index of all registers)

basys3:  # Additional boards can be defined
  device:
    min_x: 0
    max_x: 50
    # ...
  targets:
    # ...
  registers:
    # ...
```

**Key sections:**

- **device**: FPGA geometry for ACME (min/max x/y coordinates, words per frame)
- **targets**: Module definitions with spatial regions and register lists
  - `x_lo/y_lo/x_hi/y_hi`: Bounding box coordinates for ACME expansion
  - `registers`: List of reg_ids belonging to this module
  - `module`: Module name for grouping
- **registers**: Complete register index
  - Format: `id: {name: "register_name", module: "source_module"}`
  - Maps register IDs to human-readable names and modules

**Board resolution:**

The system automatically selects the board via:
1. `--board` CLI argument (explicit)
2. Auto-detect if only one board in dictionary
3. `DEFAULT_BOARD_NAME` from fi_settings.py (fallback)

**Usage:**
```bash
# Use specific board from system dictionary
python -m fi.fault_injection \
    --system-dict core/config/system_dict.yaml \
    --board xcku040 \
    --area modules
```

The system dictionary defines the complete hardware landscape. Area profiles (like `modules` and `device`) use this information to:
- Map module names to spatial coordinates
- Call ACME to expand coordinates into configuration bit addresses
- Map register IDs to module names for grouping

---

### Target pool files

Target pool files are **optional** YAML files containing explicit, pre-built target lists.

**Format:**
```yaml
targets:
  - kind: CONFIG
    module_name: "controller"
    config_address: "00001234"
  
  - kind: REG
    module_name: "lsu"
    reg_id: 128
    reg_name: "lsu_addr"
```

**Use cases:**
- Reproducing exact injection sequences
- Testing specific target combinations
- Pre-computed targets from external tools

Pool files are loaded with the `target_list` area profile:
```bash
python -m fi.fault_injection \
    --area target_list \
    --area-args "pool_file=/path/to/targets.yaml"
```

**See:** `targets/Readme.md` for complete format specification, field descriptions, and loading details.

---

### Area profile — WHERE to inject

The **area profile** defines the strategy to select targets inside the available space. Profiles live under `fi/profiles/area/` and are loaded dynamically by `profiles/area/common/loader.py`.

Each area profile module:

- is imported by name (`--area modules` → `fi.profiles.area.modules`)
- exposes:
  - `PROFILE_KIND = "area"` (constant)
  - `PROFILE_NAME` (optional; defaults to module name)
  - `describe() -> str` — Human-readable description
  - `default_args() -> dict` — Default arguments for this profile
  - `make_profile(args, *, global_seed, settings) -> AreaProfileBase` — Factory function

The `AreaProfileBase` in `fi/profiles/area/base.py` defines the core API:
```python
@dataclass
class AreaProfileBase:
    name: str
    args: Dict[str, Any]
    global_seed: Optional[int]
    
    def build_pool(
        self, 
        system_dict,
        board_name: str,
        ebd_path: str,
        cfg
    ) -> TargetPool:
        """
        Build complete TargetPool for injection.
        
        This method should:
        1. Extract relevant data from system_dict
        2. Generate/expand targets (calling ACME if needed)
        3. Apply selection strategy (ratio, ordering, etc.)
        4. Return pool with targets in injection order
        """
        raise NotImplementedError()
```

**Key difference from legacy documentation:** Area profiles do **NOT** use a `next_target()` iterator API. Instead, they build the **entire TargetPool upfront** via `build_pool()`, which returns a complete pool ready for injection.

**Available area profiles:**

- **device**: Whole-device random sampling (CONFIG and REG targets)
  - Args: `pool_size`, `ratio` (REG fraction)
- **modules**: Module-scoped injection (targets specific modules)
  - Args: `pool_size`, `ratio`, `modules` (comma-separated list)
- **target_list**: Load explicit targets from YAML file
  - Args: `pool_file` (path to YAML)
- **input**: Load external custom profile from Python file
  - Args: `module_path` (path to .py file)

**Example usage:**
```bash
# Device-wide injection
python -m fi.fault_injection \
    --area device \
    --area-args "pool_size=1000,ratio=0.3"

# Module-specific injection
python -m fi.fault_injection \
    --area modules \
    --area-args "pool_size=500,modules=controller,lsu"
```

See `profiles/area/Readme` for complete documentation on creating custom area profiles.

---
### Seed Management System

The FI system provides a three-tier seed system for reproducible campaigns:

- **Global Seed (`--global-seed`)**: Master seed that derives area and time seeds
- **Area Seed (`--area-seed`)**: Controls target selection randomness  
- **Time Seed (`--time-seed`)**: Controls injection timing randomness

If no seeds are specified, the system auto-generates them and displays them in the campaign header, allowing you to reproduce the campaign later.

**Basic usage:**
```bash
# Use global seed (area and time derived automatically)
python -m fi.fault_injection --global-seed 42 --area modules --time uniform

# Override specific seeds
python -m fi.fault_injection \
    --global-seed 42 \
    --area-seed 100 \
    --time-seed 200 \
    --area device
```

**Reproducibility:** Same seeds + same configuration = same target selection and injection timing (hardware behavior may still vary).

**See:** `core/config/Readme.md` for detailed seed derivation algorithm, auto-generation mechanism, and all configuration options.

---

#### Seed Display

Seeds are shown in the campaign header:
```
================================================================================
Campaign Configuration:
  Device: /dev/ttyUSB0 @ 1250000 baud
  Area Profile: modules
  Time Profile: uniform
  Global Seed: 42
  Area Seed: derived from global (3141592653)
  Time Seed: derived from global (2718281828)
================================================================================
```

**See:** `core/config/Readme.md` for seed manager implementation details

---

### Target Pool Export

The FI system can automatically export target pools to YAML files for inspection, reuse, and debugging.

#### Export Options

**Automatic naming (`--tpool-name`):**
```bash
python -m fi.fault_injection \
    --area modules \
    --tpool-name my_campaign
# Creates: gen/tpool/my_campaign.yaml
```

**Custom output path (`--tpool-output`):**
```bash
python -m fi.fault_injection \
    --area modules \
    --tpool-output /path/to/custom_pool.yaml
```

**Custom directory with auto-naming (`--tpool-output-dir`):**
```bash
python -m fi.fault_injection \
    --area modules \
    --tpool-output-dir /custom/dir \
    --tpool-name experiment_01
# Creates: /custom/dir/experiment_01.yaml
```

#### Generated Format

Exported pools use the same YAML format as `target_list` input:
```yaml
targets:
  - kind: CONFIG
    module_name: "ibex_controller"
    config_address: "12345678"
    pblock_name: "controller_region"
    source: "profile:modules"
  
  - kind: REG
    module_name: "ibex_load_store_unit"
    reg_id: 128
    reg_name: "addr_incr_req_i"
    source: "profile:modules"
  
  # ... (all targets in pool)
```

#### Use Cases

**Debugging area profiles:**
```bash
# Export pool to verify target selection
python -m fi.fault_injection \
    --area modules \
    --area-args "pool_size=100,modules=controller" \
    --tpool-name debug_pool

# Inspect: gen/tpool/debug_pool.yaml
# Verify: Correct modules, expected counts, proper addresses
```

**Reusing target pools:**
```bash
# Generate pool once
python -m fi.fault_injection \
    --area device \
    --area-args "pool_size=10000" \
    --tpool-name large_device_pool

# Reuse in multiple campaigns
python -m fi.fault_injection \
    --area target_list \
    --area-args "pool_file=gen/tpool/large_device_pool.yaml" \
    --time uniform

python -m fi.fault_injection \
    --area target_list \
    --area-args "pool_file=gen/tpool/large_device_pool.yaml" \
    --time poisson
```

**Sharing pools:**
```bash
# Export pool for team member
python -m fi.fault_injection \
    --area modules \
    --tpool-output /shared/pools/experiment_A.yaml

# Team member uses the same pool
python -m fi.fault_injection \
    --area target_list \
    --area-args "pool_file=/shared/pools/experiment_A.yaml"
```

**Inspecting complex profiles:**
```bash
# See what custom profile generates
python -m fi.fault_injection \
    --area input \
    --area-args "module_path=/path/to/custom.py,param=value" \
    --tpool-name custom_profile_output

# Review: gen/tpool/custom_profile_output.yaml
```

#### Notes

- Pool export happens after pool building, before campaign execution
- Export location logged to console and file
- Exported pools can be loaded with `--area target_list`
- Pool metadata (counts, statistics) included in export

---

### Debug Mode

Debug mode allows testing campaigns without hardware by stubbing the serial port.

**Enable:**
```bash
python -m fi.fault_injection --debug --area modules --time uniform
```

**Behavior:**
- Uses mock serial port (no actual UART communication)
- Injection commands logged but not sent
- Allows testing pool building, target selection, campaign scheduling, and all profile logic
- Does not perform actual hardware injection or SEM communication

**Example:**
```bash
# Test campaign without hardware
python -m fi.fault_injection \
    --debug \
    --area modules \
    --area-args "pool_size=100" \
    --time uniform \
    --time-args "duration=10,rate_hz=5" \
    --tpool-name debug_test
```

Debug mode produces full logs showing target routing and injection commands, useful for verifying campaign logic before running on hardware.

**See:** `backend/common/serial_stub.py` for implementation.

---

### Benchmark Synchronization

The FI system can synchronize with external benchmark processes using file-based signaling.

**How it works:**
1. FI waits for a signal file to appear before starting
2. Benchmark creates the file when ready
3. FI periodically checks if file still exists
4. Benchmark removes file when done → FI stops gracefully

**Basic usage:**
```bash
python -m fi.fault_injection \
    --wait-for-file /tmp/benchmark_ready \
    --area modules \
    --time uniform
```

**Configuration:**
- `--wait-for-file <path>` - Signal file path (enables sync)
- `--check-interval 1.0` - Check file every N seconds (default: 1.0)
- `--check-every-n 100` - Check file every N injections (default: 100)
- `--sync-timeout 60.0` - Max wait time in seconds (default: no timeout)

FI checks whichever comes first (time OR count) to balance responsiveness with efficiency.

**See:** `core/campaign/sync.py` for implementation details.

---

### Time profile — WHEN to inject

The **time profile** decides the campaign schedule: how often to inject, when to stop, and how to react to time constraints. Profiles live under `fi/profiles/time/` and are loaded the same way as area profiles.

Each time profile module exposes:

- `PROFILE_NAME` (optional),
- `describe() -> str`,
- `default_args() -> dict`,
- `make_profile(args: dict, *, global_seed: int | None, settings) -> TimeProfileBase`.

The `TimeProfileBase` in `fi/profiles/time/base.py` defines the core pattern:

```python
class TimeProfileBase:
    name: str
    args: Dict[str, Any]

    def describe(self) -> str: ...
    def run(self, controller) -> None: ...
```

The time profile works with an **InjectionController** instance that offers:

- `next_target() -> TargetSpec | None`,
- `inject_target(target: TargetSpec) -> bool`,
- `sleep(seconds: float) -> None`,
- `should_stop() -> bool`,
- and compatibility helpers `next_address()` / `inject_address(addr)`.

Typical TIME profiles:

- `uniform` — fixed rate or period, optional duration and shot limit,
- `ramp` — rate swept linearly from `start_hz` to `end_hz`,
- `poisson` — exponential inter-arrival times with rate `lambda_hz`,
- `microburst` — bursts of N shots separated by gaps,
- `mmpp2` — two-state Markov-modulated Poisson process,
- `trace` — replay schedule from a trace file in relative or interval mode.

---

### Injection controller and router

`fi/core/campaign/controller.py` glues everything together for the time profiles:

1. **Target selection**
   - First consumes targets from the pool (if configured),
   - then asks the area profile for more targets when the pool is exhausted.

2. **Injection**
   - Given a `TargetSpec`, calls `fi/targets/router.py`:
     - CONFIG → SEM protocol (`backend/sem/protocol.py`),
     - REG → board interface (`backend/reg_inject/reg_decoder.py`),
     - other kinds can be added without changing the controller.

3. **Time & stop conditions**
   - Exposes `sleep()` based on a monotonic clock,
   - has a `should_stop()` hook for future external stop signals.

Time profiles only see this controller, not the SEM or register injection implementation details.

---

### SEM UART and protocol

`fi/backend/sem/transport.py` wraps the serial port:

- background RX thread framing CR/LF lines,
- non-blocking TX API.

`fi/backend/sem/protocol.py` provides the SEM command layer:

- synchronisation (`sync_prompt()`),
- mode changes: Idle/Observe,
- status queries,
- injection primitive, for example `inject(address)`.

### Register injection via UART

Register injection uses the same UART connection as SEM. The fi_coms hardware module intercepts 'R' commands (2-byte format: 0x52 + register ID) and broadcasts them on the fi_port signal for register fault injection. This shared-UART architecture enables both configuration and register injection without separate hardware.

**See:** `backend/reg_inject/Readme.md` for complete architecture documentation.

---

### Logging and results layout

Logging is managed by `fi/core/logging/events.py` and `fi/core/logging/setup.py`.

- Log root is resolved as:
  - either `--log-root` (CLI),
  - or `LOG_ROOT` from `fi_settings.py` relative to the `fi/` directory.
- If `USE_RUN_SUBDIRS` is enabled in `fi_settings.py`, logs are stored as:

```text
<log_root>/<run_name>/<session>/injection_log.txt
```

Each log contains:

- Header with run/session identifiers, SEM device/baud, and profile summaries,
- Timestamped event lines, including:
  - SEM commands (TX/RX),
  - profile events,
  - errors,
  - high-level info entries.

The log writer buffers lines and flushes on shutdown.

---

### Console

The interactive SEM console in `fi/console/sem_console.py` provides an operator-friendly UART shell on top of the protocol layer:

- manual and driven modes,
- status and watch commands,
- start mode configuration,
- cheatsheets and header layout controlled by `console_settings.py`.

It can be used independently from campaigns to inspect or prepare a board.

---

## Running FI as a standalone tool

### Uniform cadence from an address list

```bash
python3 -m fi.fault_injection   --dev /dev/ttyUSB0   --baud 1250000   --run-name demo   --session s01   --system-dict path/to/system_dict.yaml   --pool-file path/to/pool.yaml   --log-root results   --area address_list   --area-args path=fi/area/addresses_example.txt,mode=sequential   --time uniform   --time-args rate_hz=5
```

This command:

- opens the SEM UART at the given device/baud,
- loads the system dictionary and pool for target expansion,
- uses `address_list` to define the address space,
- drives injections at 5 Hz,
- logs into `results/demo/s01/injection_log.txt`.

### Interactive SEM console

```bash
python3 -m fi.console.sem_console --dev /dev/ttyUSB0 --baud 1250000
```

The console exposes commands for status, watch, manual injection, and graceful exit, using the same UART and protocol infrastructure as the engine.

---

## Adding new profiles

### New AREA profile

1. Create `fi/profiles/area/<name>.py`.
2. Implement:

```python
from fi.profiles.area.base import AreaProfileBase
from fi.targets.types import TargetSpec, TargetKind
from fi import fi_settings as settings

PROFILE_KIND = "area"
PROFILE_NAME = "<name>"

def describe() -> str:
    return "Short human description."

def default_args() -> dict:
    return {
        # default key/value arguments for this profile
    }

def make_profile(args: dict, *, global_seed: int | None, settings=settings) -> AreaProfileBase:
    merged = default_args()
    merged.update(args)
    merged.setdefault("global_seed", global_seed)
    return MyAreaProfile(name=PROFILE_NAME, args=merged)

class MyAreaProfile(AreaProfileBase):
    def __post_init__(self) -> None:
        # Parse args and construct internal TargetSpec list or generator
        ...

    def next_target(self) -> TargetSpec | None:
        # Return the next TargetSpec in the sequence
        ...
```

3. Use it from the CLI:

```bash
python3 -m fi.fault_injection --area <name> --area-args key=value,...
```

### New TIME profile

1. Create `fi/profiles/time/<name>.py`.
2. Implement:

```python
from fi.profiles.time.base import TimeProfileBase
from fi import fi_settings as settings

PROFILE_KIND = "time"
PROFILE_NAME = "<name>"

def describe() -> str:
    return "Short human description."

def default_args() -> dict:
    return {
        # default key/value arguments for this profile
    }

def make_profile(args: dict, *, global_seed: int | None, settings=settings) -> TimeProfileBase:
    merged = default_args()
    merged.update(args)
    merged.setdefault("global_seed", global_seed)
    return MyTimeProfile(name=PROFILE_NAME, args=merged)

class MyTimeProfile(TimeProfileBase):
    def __post_init__(self) -> None:
        # Parse args, init RNG, precompute schedule if needed
        ...

    def run(self, controller) -> None:
        # Use controller.next_target() and controller.inject_target(target)
        # to run the campaign according to your schedule.
        ...
```

3. Use it from the CLI:

```bash
python3 -m fi.fault_injection --time <name> --time-args key=value,...
```

Profiles are discovered by module name; no central registry needs to be updated.

---
## Command-Line Interface Reference

### Serial & Hardware
```bash
--dev DEVICE              # Serial device (default: /dev/ttyUSB0)
--baud RATE               # Baud rate (default: 1250000)
--board NAME              # Board name from system dictionary
```

### SEM Configuration
```bash
--sem-clock-hz HZ         # SEM clock frequency (default: 100000000)
--sem-preflight-required  # Require SEM preflight test
--sem-no-preflight        # Skip SEM preflight test
```

### Register Injection Configuration
```bash
--reg-inject-disabled     # Disable register injection (use NoOp)
--reg-inject-idle-id ID   # Idle register ID value (default: 0)
--reg-inject-reg-id-width BITS  # Register ID bit width (default: 8)
```

### Area Profile Configuration
```bash
--area PROFILE            # Area profile name (device, modules, target_list, input)
--area-args ARGS          # Profile arguments (comma-separated key=value pairs)
                          # Examples: "pool_size=1000,ratio=0.3"
                          #           "modules=controller,lsu"
                          #           "pool_file=/path/to/targets.yaml"
```

### Time Profile Configuration
```bash
--time PROFILE            # Time profile name (uniform, ramp, poisson, microburst, mmpp2, trace)
--time-args ARGS          # Profile arguments (comma-separated key=value pairs)
                          # Examples: "duration=60,rate_hz=10"
                          #           "shots=100,period=1.0"
                          #           "start_hz=1,end_hz=10"
```

### Target Pool Configuration
```bash
--tpool-name NAME         # Export pool to gen/tpool/<name>.yaml
--tpool-output PATH       # Export pool to specific path
--tpool-output-dir DIR    # Export pool to custom directory
```

### Seed Configuration
```bash
--global-seed SEED        # Master seed (derives area/time seeds)
--area-seed SEED          # Area profile seed (overrides derived)
--time-seed SEED          # Time profile seed (overrides derived)
```

### Logging Configuration
```bash
--log-level LEVEL         # Verbosity (minimal, normal, verbose)
--log-root DIR            # Log output directory
```

### System Configuration
```bash
--system-dict PATH        # System dictionary YAML file
--ebd-path PATH           # EBD file path (for ACME)
--debug                   # Enable debug mode (no hardware)
```

### Benchmark Synchronization
```bash
--wait-for-file PATH      # Signal file for benchmark coordination
--check-interval SEC      # Check file every N seconds (default: 1.0)
--check-every-n COUNT     # Check file every N injections (default: 100)
--sync-timeout SEC        # Max wait time for signal file (default: none)
```

**For complete help with current defaults:**
```bash
python -m fi.fault_injection --help
```

---

## Integration with FATORI‑V

When used under FATORI‑V, the FI engine is treated as an external console:

- FATORI‑V parses the main run YAML and decides:
  - which area/time profiles to use,
  - which arguments they receive,
  - where the logs should be placed,
  - which system dictionary and pool files to generate.
- FATORI‑V calls the FI engine with a command equivalent to:

```bash
python3 -m fi.fault_injection   --dev <serial_dev>   --baud <baud>   --run-name <run_id>   --session <benchmark_label>   --system-dict <path/to/system_dict.yaml>   --pool-file <path/to/pool.yaml>   --log-root results   --area <area_profile>   --area-args "..."   --time <time_profile>   --time-args "..."   --seed <seed>   --on-end exit
```

The FI engine remains independent from the run YAML and only depends on its CLI and the dictionary/pool files it is given.

---

## Related Documentation

### Core Systems
- [Configuration System](core/config/Readme.md) - Config dataclass, CLI parser, seed management
- [Logging System](core/logging/Readme.md) - Event-based logging, verbosity levels
- [Campaign Controller](core/campaign/Readme.md) - Injection execution and orchestration

### Backends
- [Backend Overview](backend/Readme.md) - All backend subsystems
- [SEM Backend](backend/sem/Readme.md) - Configuration bit injection via SEM IP Core
- [Register Injection](backend/reg_inject/Readme.md) - UART-based register injection
- [ACME Backend](backend/acme/Readme.md) - Address expansion and caching

### Profiles
- [Profile System](profiles/Readme.md) - Area and time profile overview
- [Area Profiles](profiles/area/Readme) - Target selection (WHERE to inject)
- [Time Profiles](profiles/time/Readme) - Campaign scheduling (WHEN to inject)

### Targets
- [Target System](targets/Readme.md) - TargetSpec, TargetPool, and routing

### Console
- [Interactive Console](console/Readme.md) - Manual SEM control

### See Also
- `fi_settings.py` - Default configuration values
- `fault_injection.py` - Main entry point
