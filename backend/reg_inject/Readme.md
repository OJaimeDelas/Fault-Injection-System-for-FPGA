# Register Injection Backend

UART-based register fault injection via the fi_coms hardware module.

## Overview

The register injection backend enables fault injection into CPU registers using a UART-based command protocol. Unlike traditional GPIO-based approaches that require dedicated pins and complex timing, this backend shares the same UART connection used for SEM communication.

### Key Features

- **Shared UART**: Uses the same serial connection as SEM (no additional hardware)
- **fi_coms Protocol**: Hardware module intercepts 'R' commands for register injection
- **Fire-and-forget**: Non-blocking injection for precise campaign timing
- **Transport Sharing**: Both SEM and register injection use a single `SemTransport` instance
- **Conditional Initialization**: Only initialized when REG targets exist in the pool

### When It's Used

Register injection is automatically enabled when:
1. The system dictionary contains register definitions
2. The target pool includes REG-kind targets
3. `--reg-inject-disabled` flag is NOT set

The backend is initialized conditionally based on `get_backend_requirements()` analysis of the target pool.

---

## Architecture

### UART-Based Design

Unlike GPIO pin manipulation, register injection uses UART commands sent over the shared serial connection:
```
FI System
    │
    ├─ SEM Backend ──────────> write_line('I 12345678\r')
    │                                  │
    ├─ Register Injection ────> write_bytes(b'R\x63')
    │                                  │
    └────────── Shared UART ───────────┘
                      │
                 [fi_coms.v]
                      │
          ┌───────────┴──────────┐
          ↓                      ↓
     SEM IP Core          fi_port[7:0]
    (config bits)                │
          │                      │
          ↓                      ↓
    FPGA Logic            Register Injection
```

### fi_coms Hardware Module

The `fi_coms.v` Verilog module acts as a UART command router:

**Responsibilities:**
- Receive UART commands from computer
- Intercept 'R' commands for register injection
- Forward all other commands to SEM IP Core transparently
- Maintain single UART connection for both backends
- Queue register injections in 32-entry FIFO

**Command Routing:**
- **'R' commands**: Intercepted → Queued in FIFO → Broadcast on `fi_port`
- **All other commands**: Passed through → SEM IP Core → Normal operation

**Key Parameters:**
- `CLOCK_FREQ_HZ`: System clock frequency (default: 100 MHz)
- `BAUD_RATE`: UART baud rate (default: 1.25 Mbaud)
- `DEBUG`: Enable acknowledgment messages (0=production, 1=testing)

### Transport Sharing

Both SEM and register injection backends share a single `SemTransport` instance:

**SemTransport API:**
```python
# For SEM commands (text-based, line-terminated)
transport.write_line('I 12345678\r')

# For register injection (binary, no termination)
transport.write_bytes(b'R\x63')
```

**Initialization Flow:**
```python
# In fault_injection.py
if backend_reqs["sem"] or backend_reqs["reg_inject"]:
    # Open single transport for both backends
    transport, _ = open_sem(cfg, log_ctx)

if backend_reqs["sem"]:
    # SEM protocol uses text commands
    sem_proto = SemProtocol(transport)

if backend_reqs["reg_inject"]:
    # Register injection uses binary commands
    board_if = create_board_interface(cfg, transport=transport)
```

---

## fi_coms Protocol

### Components

**File:** `backend/reg_inject/board_interface.py`

**Three implementations:**

1. **`BoardInterface`** (abstract base class)
   - Defines `inject_register()` interface
   - MUST be non-blocking (fire-and-forget)

2. **`UARTBoardInterface`** (production)
   - Validates register ID against configured width
   - Sends 2-byte fi_coms command via `transport.write_bytes()`
   - Returns immediately (no acknowledgment wait)

3. **`NoOpBoardInterface`** (testing)
   - Logs injection requests without hardware communication
   - Used when `--reg-inject-disabled` flag set

**Factory function** `create_board_interface(cfg, transport)` selects appropriate implementation based on configuration.

**Usage example:**
```python
board_if = create_board_interface(cfg, transport=transport)
success = board_if.inject_register(reg_id=99)
```

**See source file** for complete implementation details.

## Configuration

### Settings (fi_settings.py)
```python
# Register Injection Configuration (UART-based via fi_coms)
# =============================================================================

# Force register injection to remain disabled even when REG targets exist
INJECTION_REG_FORCE_DISABLED = False

# Idle register ID value (sent when no injection active)
INJECTION_REG_IDLE_ID = 0

# Bit width for register ID transmission (8 bits = IDs 1-255)
INJECTION_REG_ID_WIDTH = 8
```

### CLI Arguments
```bash
# Disable register injection (use NoOp interface)
--reg-inject-disabled

# Set idle register ID (default: 0)
--reg-inject-idle-id <ID>

# Set register ID bit width (default: 8, supports 1-255)
--reg-inject-reg-id-width <BITS>
```
---

## Integration Guide

### When Register Injection is Initialized

Register injection is conditionally initialized when:
- Target pool contains REG-kind targets (detected by `get_backend_requirements()`)
- `--reg-inject-disabled` flag NOT set

See `fault_injection.py` for initialization logic.

### Transport Sharing

Both SEM and register injection share a single UART transport. The transport is opened once and passed to both backend initialization functions.

### Register ID Validation

The board interface validates register IDs (1 to max_reg_id based on configured bit width) before sending commands. Out-of-range IDs are logged as errors and injection is skipped.

**Example Error:**
```
[REG_INJECT] ERROR: reg_id=256 out of range (1-255 for 8-bit width)
```

### Error Handling

**Out of Range Register IDs:**
- Validation fails before sending command
- Error logged to file and console
- Injection skipped, campaign continues

**Missing Transport:**
- Placeholder mode activated
- Warning logged: "[REG_INJECT] No transport available - returning success (placeholder)"
- Injection simulated, campaign continues
- Useful for dry-run testing

**Hardware Issues:**
- UART write errors caught by transport layer
- Register injection backend doesn't block or wait for confirmation
- Campaign timing maintained even if hardware fails

### Placeholder Mode

When no transport is available (e.g., debug mode without hardware):
```python
if self.transport is None:
    log_reg_inject_placeholder()
    return True  # Simulate success
```

This allows:
- Testing campaign logic without hardware
- Dry-run verification of target selection
- Profile development and debugging

---

## Related Documentation

- [Backend Overview](../Readme.md) - All backend subsystems
- [SEM Backend](../sem/Readme.md) - Configuration bit injection
- [ACME Backend](../acme/Readme.md) - Address expansion
- [Target System](../../targets/Readme.md) - TargetSpec and TargetPool
- [Config System](../../core/config/Readme.md) - Configuration management
- [Main README](../../Readme.md) - System overview

## See Also

- `fi_settings.py` - Default register injection settings
- `fault_injection.py` - Backend initialization logic
- `targets/router.py` - Target routing to backends