# FI Backend - SEM Protocol

Communication layer for Xilinx SEM IP core via UART.

## Overview

The SEM (Soft Error Mitigation) protocol provides methods for:
- State management (Idle, Observe modes)
- Status queries (error counters, state)
- Fault injection (fire-and-forget for campaigns)

## Architecture
```
SemProtocol (protocol.py)
    ↓
SemTransport (transport.py)
    ↓
Serial/UART (pyserial or stub)
```

## Files

- `transport.py` - UART I/O, background RX reader, CR/LF framing
- `protocol.py` - SEM command wrappers (sync, state, status, inject)
- `setup.py` - Connection initialization and preflight

## Injection Behavior

### Campaign Mode (Default)

Fault injection uses **fire-and-forget** for timing accuracy:
```python
sem_proto.inject_lfa("00001234")
# Returns immediately - no waiting for response
```

**Why fire-and-forget:**
- Time profiles need precise injection timing
- SEM IP processes commands asynchronously  
- Response collection adds 300ms delay per injection
- At 10 Hz target rate, waiting causes 75% slowdown

**What happens:**
1. Command `N <address>` sent to SEM IP
2. Method returns immediately (~0.1ms)
3. SEM IP processes injection asynchronously
4. No acknowledgment waited for

### Setup/Console Mode

State management and status commands **do wait** for responses:
```python
sem_proto.goto_idle()      # Waits for "I>" prompt
sem_proto.status()         # Waits for counter values  
sem_proto.goto_observe()   # Waits for "O>" prompt
```

These commands are used during:
- Initial connection setup
- Preflight verification
- Interactive console (not campaigns)

## Timing Requirements

**Critical:** `inject_lfa()` must remain non-blocking for campaigns.

If response verification is needed, it should be:
- Separate method (not inject_lfa)
- Used only in setup/console, never during campaigns
- Never added to the injection path

## Usage Example
```python
# Setup (waits for responses)
transport = SemTransport(port, baud)
sem_proto = SemProtocol(transport)
sem_proto.sync_prompt()           # Wait for initial prompt
sem_proto.goto_observe()          # Wait for mode change

# Campaign (fire-and-forget)
for address in addresses:
    sem_proto.inject_lfa(address)  # Returns immediately
    # No waiting - next injection can proceed
```

## Connection Setup

The `setup.py` module handles:
- Serial port opening
- Preflight SEM state verification
- Error detection during initialization

Setup commands use response collection because we need to verify
the board is ready before starting campaigns. Once verified,
injections use fire-and-forget for speed.

## Debug Mode

In debug mode (`--debug` flag), `serial_stub.py` provides a mock
serial port that simulates SEM responses without hardware. This
allows testing campaign timing without a physical board.

The stub maintains timing accuracy by:
- No delay in `open()`
- Minimal delays in `write()/read()` (~0.008ms per byte)
- No response collection delays

## Related Documentation

### Backend Systems
- [Backend Overview](../Readme.md) - All backend subsystems
- [Register Injection](../reg_inject/Readme.md) - Shares UART transport with SEM
- [ACME Backend](../acme/Readme.md) - Generates configuration addresses

### Core Systems
- [Main README](../../Readme.md) - System overview
- [Config System](../../core/config/Readme.md) - SEM configuration settings
- [Campaign Controller](../../core/campaign/Readme.md) - Uses SEM for CONFIG injection

### Targets
- [Target System](../../targets/Readme.md) - CONFIG targets route to SEM

### See Also
- `fi_settings.py` - SEM default settings (clock, preflight, etc.)
- `fault_injection.py` - SEM initialization and setup
- `targets/router.py` - Routes CONFIG targets to SEM backend
- `transport.py` - UART layer implementation details
- `protocol.py` - Full SEM command reference
- `setup.py` - Connection initialization