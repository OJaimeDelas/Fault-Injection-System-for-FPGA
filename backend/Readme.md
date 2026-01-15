# FI Backend Subsystems

Hardware communication backends for fault injection.

## Overview

The `backend/` directory contains all subsystems responsible for communicating with hardware to perform fault injections. Backends are independent modules that handle different injection mechanisms.

### Backend Responsibilities

- **Hardware Communication**: UART, SPI, GPIO, or other protocols
- **Command Protocol**: Format and send injection commands
- **Transport Management**: Serial port, network, or mock connections
- **Error Handling**: Validate commands, handle hardware failures
- **Conditional Initialization**: Only initialize when needed

### Backend vs Profile Distinction

**Backends** (this directory):
- **WHAT** to do: Send commands to hardware
- **HOW** to communicate: UART protocol, command formatting
- **Physical layer**: Actual injection into FPGA

**Profiles** (`profiles/` directory):
- **WHICH** targets to inject: Target selection logic
- **WHEN** to inject: Campaign scheduling and timing
- **High-level logic**: Campaign orchestration

---

## Backend Subsystems

### SEM Backend

**Purpose:** Configuration bit injection via SEM IP Core

**Location:** `backend/sem/`

**Components:**
- `transport.py`: UART communication layer
  - Background RX thread with line framing
  - Non-blocking TX API
  - Thread-safe buffer management
- `protocol.py`: SEM command protocol
  - Synchronization (`sync_prompt()`)
  - Mode management (Idle/Observe/Injection)
  - Status queries
  - Configuration bit injection (`inject_lfa()`)
- `setup.py`: Connection and preflight checks
  - Serial port detection
  - SEM initialization
  - Preflight test (optional)

**When Initialized:**
- CONFIG targets present in target pool
- Detected by `get_backend_requirements()` analysis

**Fire-and-Forget Design:**
- SEM commands sent without waiting for completion
- Critical for maintaining precise campaign timing
- SEM responses monitored by background thread

**Usage Example:**
```python
from fi.backend.sem.setup import open_sem

# Open connection and get protocol wrapper
transport, sem_proto = open_sem(cfg, log_ctx)

# Inject configuration bit at address
sem_proto.inject_lfa(address="12345678")
```

**See:** `backend/sem/Readme.md` for complete documentation

---

### Register Injection Backend

**Purpose:** Register injection via UART fi_coms protocol

**Location:** `backend/reg_inject/`

**Components:**
- `board_interface.py`: UART-based injection interface
  - `BoardInterface` abstract base class
  - `UARTBoardInterface` for UART fi_coms commands
  - `NoOpBoardInterface` for testing without hardware
  - Factory function: `create_board_interface()`
- `reg_decoder.py`: Register target injection helper
  - Routes REG targets to board interface
  - Extracts reg_id from TargetSpec
  - Handles errors and logging

**When Initialized:**
- REG targets present in target pool
- Detected by `get_backend_requirements()` analysis
- Shares UART transport with SEM backend

**Architecture:**
- Uses same UART connection as SEM (no separate hardware)
- fi_coms hardware module intercepts 'R' commands
- Binary protocol: 'R' (0x52) + register ID byte
- Fire-and-forget: No blocking, no acknowledgment wait

**Usage Example:**
```python
from fi.backend.reg_inject.board_interface import create_board_interface

# Create interface (uses shared transport)
board_if = create_board_interface(cfg, transport=transport)

# Inject register ID 99
success = board_if.inject_register(reg_id=99)
```

**See:** `backend/reg_inject/Readme.md` for complete documentation

---

### ACME Backend

**Purpose:** Address expansion (coordinates → configuration addresses)

**Location:** `backend/acme/`

**Components:**
- `factory.py`: Board-specific decoder factory
  - Automatic board detection
  - Decoder instantiation
- `cache.py`: Address caching system
  - Persistent cache across campaigns
  - Cache validation and loading
  - Significant speedup for repeated expansions
- `decoder.py`: Base decoder class
  - Abstract interface for ACME implementations
- `basys3.py`: Basys3-specific decoder
  - Device geometry for Basys3 FPGA
- `xcku040.py`: KU040-specific decoder
  - Device geometry for KU040 FPGA
- `geometry.py`: Geometric utilities
  - Coordinate validation
  - Bounding box operations

**When Used:**
- Area profiles need address expansion (e.g., `device`, `modules`)
- System dictionary provides spatial coordinates
- ACME decoder converts (x, y, bit) → configuration address

**Caching:**
- First expansion: Computes and caches addresses
- Subsequent expansions: Loads from cache (100x+ faster)
- Cache stored in `gen/acme/<board>_<region>.txt`

**Usage Example:**
```python
from fi.backend.acme.factory import create_acme_decoder

# Create board-specific decoder
acme = create_acme_decoder(board_name, system_dict, ebd_path, cache_dir)

# Expand coordinates to configuration addresses
addresses = acme.expand_region(x_lo, y_lo, x_hi, y_hi)
# Returns: List of LFA address strings
```

**See:** `backend/acme/Readme.md` for complete documentation

---

## Common Utilities

**Location:** `backend/common/`

### Serial Stub

**File:** `serial_stub.py`

**Purpose:** Mock serial port for debug mode

**Usage:**
- Enabled with `--debug` flag
- No actual UART communication
- Injection commands logged but not sent
- Allows testing campaign logic without hardware

**What Works in Debug Mode:**
- Pool building
- Target selection
- Campaign scheduling
- Logging system
- All profiles

**What Doesn't Work:**
- Actual hardware injection
- SEM communication
- Real-time hardware verification

**Example:**
```bash
# Test campaign without hardware
python -m fi.fault_injection \
    --debug \
    --area modules \
    --time uniform \
    --time-args "duration=10,rate_hz=1"
```

---

## Backend Initialization

### Conditional Initialization

Backends are only initialized when needed, determined by target pool analysis:
```python
# In fault_injection.py
backend_reqs = pool.get_backend_requirements()
# Returns: {"sem": bool, "reg_inject": bool}

# Example results:
# - CONFIG-only pool: {"sem": True, "reg_inject": False}
# - REG-only pool: {"sem": False, "reg_inject": True}
# - Mixed pool: {"sem": True, "reg_inject": True}
```

### Transport Sharing

SEM and register injection share a single UART connection. The transport is opened once and passed to both backends during initialization.

**See:** `backend/reg_inject/Readme.md` for transport sharing details.

### Initialization Order

1. **Target Pool Analysis**: Determine which backends needed
2. **Transport Opening**: Open single UART connection (if any backend needs it)
3. **SEM Initialization**: Create SEM protocol wrapper (if CONFIG targets)
4. **Register Injection Initialization**: Create board interface (if REG targets)
5. **ACME Initialization**: Load decoder (if address expansion needed)

---

## Related Documentation

- [SEM Backend](sem/Readme.md) - Configuration bit injection
- [Register Injection Backend](reg_inject/Readme.md) - Register injection
- [ACME Backend](acme/Readme.md) - Address expansion
- [Target System](../targets/Readme.md) - TargetSpec and routing
- [Config System](../core/config/Readme.md) - Configuration management
- [Campaign Controller](../core/campaign/Readme.md) - Campaign execution
- [Main README](../Readme.md) - System overview

## See Also

- `fault_injection.py` - Backend initialization logic
- `targets/router.py` - Target routing to backends
- `fi_settings.py` - Default backend settings
