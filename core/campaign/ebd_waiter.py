# =============================================================================
# FATORI-V • FI Campaign EBD Waiter
# File: ebd_waiter.py
# -----------------------------------------------------------------------------
# Waits for EBD file to appear before proceeding with pool build.
# =============================================================================

import time
from pathlib import Path
from typing import Optional

from fi.core.logging.events import log_ebd_waiting, log_ebd_ready


def wait_for_ebd_file(ebd_path: str, timeout_s: Optional[float] = None, check_interval_s: float = 1.0) -> bool:
    """
    Wait for EBD file to exist before proceeding.
    
    If EBD path is provided but file doesn't exist, this function
    will poll until the file appears or timeout expires.
    
    Args:
        ebd_path: Path to EBD file
        timeout_s: Maximum time to wait (None = wait indefinitely)
        check_interval_s: How often to check for file existence
    
    Returns:
        True if file exists/appeared, False if timeout expired
    """
    if not ebd_path:
        # No EBD path provided - nothing to wait for
        return True

    ebd_file = Path(ebd_path)

    if ebd_file.exists():
        # File already present - ready immediately
        log_ebd_ready(ebd_path, 0.0)
        return True

    # File not yet present - start polling
    log_ebd_waiting(ebd_path)

    start_time = time.time()

    while True:
        if ebd_file.exists():
            elapsed = time.time() - start_time
            log_ebd_ready(ebd_path, elapsed)
            return True

        # Check timeout
        if timeout_s is not None:
            elapsed = time.time() - start_time
            if elapsed >= timeout_s:
                return False

        time.sleep(check_interval_s)