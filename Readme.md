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
  Readme                    # This file
  fi_settings.py            # Engine defaults (serial, SEM freq, logging, etc.)
  fault_injection.py        # Main console for driven campaigns (python -m fi.fault_injection)

  engine/
    config.py               # Config dataclass built from CLI + fi_settings
    logging_setup.py        # Resolves log_root and opens per-session logger
    sem_setup.py            # UART transport + SEM protocol preflight
    profile_loader.py       # Dynamic loader for area/time profile modules
    injection_controller.py # Glue: profiles + targets + SEM + logging

  profiles/
    area/
      Readme                # How to write and use AREA profiles
      base.py               # Base class for AREA profiles (next_target API)
      address_list.py       # AREA profile: config_bit targets from a text file
      # device.py           # AREA profile: whole-device ACME-derived targets
      # modules.py          # AREA profile: module/pblock-scoped ACME targets

    time/
      Readme                # How to write and use TIME profiles
      base.py               # Base class for TIME profiles (run(controller) API)
      uniform.py            # TIME profile: constant cadence (Hz or period)
      ramp.py               # TIME profile: rate ramp between two values
      poisson.py            # TIME profile: exponential inter-arrival times
      microburst.py         # TIME profile: fixed-size bursts separated by gaps
      mmpp2.py              # TIME profile: 2-state Markov-modulated Poisson
      trace.py              # TIME profile: schedule from a time trace file

  targets/
    Readme                  # Target abstraction, pools, and dictionary format
    types.py         # TargetSpec and TargetKind definitions
    pool.py          # In-memory pool of TargetSpec (filter/shuffle/pop)
    dict_loader.py          # System dictionary loader (board, regs, modules, pblocks)
    pool_loader.py          # Injection pool loader/expander (YAML → TargetPool)
    acme_sem_decoder.py     # ACME/EBD interface for config-bit targets
    gpio_reg_decoder.py     # Board/GPIO interface for register targets
    router.py               # Central dispatch: TargetSpec → SEM or GPIO backend

  semio/
    transport.py            # UART I/O, background RX reader, CR/LF framing
    protocol.py             # SEM helpers: sync, modes, status, inject

  log/
    events.py               # Deferred writer for per-session logs

  console/
    sem_console.py          # Interactive console (manual/driven)
    console_settings.py     # Colors, headers, section styles, prompt behaviour

  cli/
    parser.py               # Central argparse configuration for the engine
    Readme                  # CLI documentation
```

---

## Conceptual model

### Targets and pools

The engine never works directly with “raw addresses” or “register IDs” in its core logic. Instead it uses **TargetSpec** objects defined in `fi/targets/types.py`.

A `TargetSpec` describes **what** to inject:

- `kind` identifies the category:
  - `config_bit` — configuration bit / frame address for SEM,
  - `reg_id` / `reg_bit` — register-level fault injection,
  - `module` / `pblock` / `frame` — higher-level labels used before expansion.
- Optional fields carry concrete details:
  - `config_address`, `frame_address`,
  - `reg_id`, `bit_index`,
  - `module_name`, `pblock_name`,
  - `tags` (grouping, filtering), `source`, and arbitrary `meta`.

A collection of targets is stored in a **TargetPool** (`fi/targets/pool.py`):

- `add()` / `add_many()` to build the pool,
- `filtered(kind=..., module=..., tags=...)` for views,
- `shuffled(seed)` for deterministic randomisation,
- `pop_next()` for simple iteration.

The engine builds an initial pool via `fi/targets/pool_loader.py` from an **injection pool YAML file**.

---

### System dictionary and injection pool

Hardware description is centralised in a **system dictionary** loaded by `fi/targets/dict_loader.py`. The dictionary is a YAML file and typically contains:

```yaml
board:
  name: "xcku040"
  ebd_path: "build/design.ebd"
  acme_cache_dir: "build/acme_cache"

registers:
  - id: 0
    name: "alu_reg0"
    module: "ibex_core.alu"
    bits: 32
  - id: 1
    name: "alu_reg1"
    module: "ibex_core.alu"
    bits: 32

modules:
  "ibex_core.alu":
    description: "Integer ALU registers"
    pblock: "ALU_PB0"

pblocks:
  "ALU_PB0":
    region: "CLOCKREGION_X1Y2:CLOCKREGION_X1Y3"
```

This file defines:

- **Board** and ACME context (`name`, `ebd_path`, `acme_cache_dir`),
- **Register inventory** (`id`, human name, module, width),
- **Module map** (module name → pblock, description, extra metadata),
- **Pblock map** (pblock name → region constraint).

On top of the dictionary, an **injection pool** YAML file describes high-level target entries to use for a campaign. Example:

```yaml
targets:
  - kind: reg_id
    id: 0
    tags: ["alu", "regs"]

  - kind: config_bit
    address: "0x00123456"
    tags: ["manual"]

  - kind: module
    name: "ibex_core.alu"
    include_regs: true
    include_config: true
    tags: ["alu"]

  - kind: pblock
    name: "ALU_PB0"
    include_config: true
    tags: ["alu_region"]
```

`pool_loader.build_initial_pool(system_dict, pool_file)` expands these entries into concrete `TargetSpec` instances by:

- mapping `reg_id` to register metadata,
- wrapping direct `config_bit` addresses,
- expanding `module` entries into:
  - register targets (reg_id) for that module,
  - configuration-bit targets via ACME, using the module’s pblock,
- expanding `pblock` entries into configuration-bit targets via ACME.

---

### Area profile — WHERE to inject

The **area profile** defines the strategy to select targets inside the available space. Profiles live under `fi/profiles/area/` and are loaded dynamically by `engine/profile_loader.py`.

Each area profile module:

- is imported by name (`--area address_list` → `fi.profiles.area.address_list`),
- exposes:
  - `PROFILE_NAME` (optional; defaults to module name),
  - `describe() -> str`,
  - `default_args() -> dict`,
  - `make_profile(args: dict, *, global_seed: int | None, settings) -> AreaProfileBase`.

The `AreaProfileBase` in `fi/profiles/area/base.py` defines the core API:

```python
class AreaProfileBase:
    name: str
    args: Dict[str, Any]

    def describe(self) -> str: ...
    def next_target(self) -> TargetSpec | None: ...
    def reset(self) -> None: ...
    # Compatibility helper:
    def next_address(self) -> str | None: ...
```

During a campaign, the engine asks the area profile for the next target via `next_target()`. For legacy address-based code, `next_address()` is available and simply unwraps `config_bit` targets.

#### Example: `address_list` profile

`fi/profiles/area/address_list.py` loads a text file of addresses and turns each line into a `config_bit` `TargetSpec`:

```text
0x00123456
0x00123478
# Comment lines are ignored
0x0012349A
```

Arguments (via `--area-args`):

- `path`    — path to the file (required),
- `mode`    — `sequential` or `random`,
- `seed`    — optional seed for random mode,
- `tags`    — optional comma-separated tags to attach to all targets.

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
     - `config_bit` → SEM protocol (`semio/protocol.py`),
     - `reg_id` / `reg_bit` → board interface (`gpio_reg_decoder.py`),
     - other kinds can be added without changing the controller.

3. **Time & stop conditions**
   - Exposes `sleep()` based on a monotonic clock,
   - has a `should_stop()` hook for future external stop signals.

Time profiles only see this controller, not the SEM or GPIO details.

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
