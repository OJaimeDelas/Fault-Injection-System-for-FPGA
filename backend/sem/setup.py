# =============================================================================
# FATORI-V • FI Engine SEM Setup
# File: engine/sem_setup.py
# -----------------------------------------------------------------------------
# Helper functions to open the SEM serial transport and protocol wrapper.
#=============================================================================

from __future__ import annotations

from typing import Tuple, Dict

from fi import fi_settings
from fi.backend.sem.transport import SemTransport, SerialConfig
from fi.backend.sem.protocol import SemProtocol
from fi.console import console_settings

from fi.core.config.config import Config

def open_sem(cfg: Config, log_ctx: Dict) -> Tuple[SemTransport, SemProtocol]:
    """
    Open the serial connection to the SEM IP and build the SemProtocol object.

    This function:
      - Creates SerialConfig with device and baud settings
      - Instantiates SemTransport with the config
      - Opens the serial port and starts the reader thread
      - Instantiates SemProtocol with the transport
      - Optionally performs a preflight test to verify SEM responds

    Returns:
        (transport, protocol)
    """
    from fi.core.logging.events import log_error
    
    # Create SerialConfig object
    serial_config = SerialConfig(
        device=cfg.dev,
        baud=cfg.baud
    )
    
    # Instantiate transport with config
    transport = SemTransport(cfg=serial_config)
    
    # Open serial port
    transport.open()
    
    # Start background reader thread
    transport.start_reader()

    # Instantiate protocol
    proto = SemProtocol(tr=transport)

    # Preflight test if enabled
    if getattr(console_settings, 'SEM_PREFLIGHT_TEST', True):
        print("[SEM] Testing connection...")
        try:
            # Sync to prompt
            proto.sync_prompt()
            
            # Send status command to verify communication
            status = proto.status()
            
            if not status:
                log_error("SEM preflight test: No response to status command")
                print("[SEM] ERROR: No response from SEM. Check hardware connection.")
                
                # Check if preflight is required - abort or warn
                if cfg.sem_preflight_required:
                    print("[SEM] SEM_PREFLIGHT_REQUIRED=True - aborting campaign.")
                    transport.close()
                    raise RuntimeError("SEM preflight failed: No response from SEM")
                else:
                    print("[SEM] Preflight not required - continuing with warning.")
            else:
                print(f"[SEM] Connection OK - received {len(status)} status fields")
                
        except RuntimeError:
            # Re-raise our own RuntimeError (preflight required failure)
            raise
        except Exception as e:
            log_error(f"SEM preflight test failed", exc=e)
            print(f"[SEM] ERROR: Preflight test failed: {e}")
            
            # Check if preflight is required - abort or warn
            if cfg.sem_preflight_required:
                print("[SEM] SEM_PREFLIGHT_REQUIRED=True - aborting campaign.")
                transport.close()
                raise RuntimeError(f"SEM preflight failed: {e}")
            else:
                print("[SEM] Preflight not required - continuing with warning.")

    return transport, proto