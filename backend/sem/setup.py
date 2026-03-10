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
        baud=cfg.baud,
        debug=cfg.debug
    )
    
    # Instantiate transport with config
    transport = SemTransport(cfg=serial_config)
    
    # Open serial port
    transport.open()
    
    # Start background reader thread
    transport.start_reader()

    # Instantiate protocol
    proto = SemProtocol(tr=transport)

    # Run SEM preflight test if required (fi_settings.SEM_PREFLIGHT_REQUIRED)
    # FPGA needs time to boot after EBD generation before SEM IP responds
    # Retry multiple times with delays to handle boot time
    if cfg.sem_preflight_required:
        from fi.core.logging.events import log_sem_preflight_testing
        import time
        
        log_sem_preflight_testing()
        
        # Get retry configuration from fi_settings
        timeout = getattr(fi_settings, 'SEM_PREFLIGHT_TIMEOUT', 60.0)
        retry_interval = getattr(fi_settings, 'SEM_PREFLIGHT_RETRY_INTERVAL', 5.0)
        
        start_time = time.time()
        attempt = 0
        last_error = None
        
        while time.time() - start_time < timeout:
            attempt += 1
            
            try:
                # Sync to prompt
                proto.sync_prompt()
                
                # Send status command to verify communication
                status = proto.status()
                
                if status:
                    # Success! SEM is responding
                    from fi.core.logging.events import log_sem_preflight_ok
                    log_sem_preflight_ok(len(status))
                    break
                else:
                    last_error = "no_response"
                    
            except Exception as e:
                last_error = str(e)
            
            # Failed this attempt - check if we should retry
            elapsed = time.time() - start_time
            if elapsed < timeout:
                # Wait before retry
                time.sleep(retry_interval)
            else:
                # Timeout exceeded - fail
                log_error(f"SEM preflight exhausted all retries ({attempt} attempts over {elapsed:.1f}s)")
                from fi.core.logging.events import log_sem_preflight_error
                log_sem_preflight_error(last_error or "timeout", required=True)
                transport.close()
                raise RuntimeError(f"SEM preflight failed after {attempt} attempts: {last_error}")
        else:
            # While loop completed without break - timeout exceeded
            elapsed = time.time() - start_time
            log_error(f"SEM preflight timeout after {attempt} attempts over {elapsed:.1f}s")
            from fi.core.logging.events import log_sem_preflight_error
            log_sem_preflight_error(last_error or "timeout", required=True)
            transport.close()
            raise RuntimeError(f"SEM preflight failed: timeout after {attempt} attempts")

    return transport, proto