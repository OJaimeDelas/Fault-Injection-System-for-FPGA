# =============================================================================
# FATORI-V • FI Engine
# File: cleanup.py
# -----------------------------------------------------------------------------
# Resource cleanup helper for graceful shutdown.
#=============================================================================

from typing import Optional


def cleanup_resources(transport=None, log_ctx=None):
    """
    Clean up resources before exit.
    
    This helper ensures all resources are properly released:
    1. Close SEM transport connection (if open)
    2. Close log file (if open)
    
    All cleanup operations are wrapped in try-except to ensure
    cleanup continues even if individual operations fail.
    
    Args:
        transport: SEM transport instance (may be None)
        log_ctx: Logging context (may be None)
    """
    # Close SEM transport
    if transport is not None:
        try:
            transport.close()
        except Exception:
            # Ignore errors during cleanup
            pass
    
    # Close log file
    if log_ctx is not None:
        try:
            from fi.log import events
            events.close_log_file()
        except Exception:
            # Ignore errors during cleanup
            pass