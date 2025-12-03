# =============================================================================
# FATORI-V • FI Engine
# File: signal_handler.py
# -----------------------------------------------------------------------------
# Signal handler for graceful campaign shutdown on Ctrl+C and SIGTERM.
#=============================================================================

import sys
import signal
from typing import Optional


# Module-level controller reference for signal handlers
# Set during campaign execution to enable graceful shutdown
_active_controller = None


def setup_signal_handlers():
    """
    Install signal handlers for graceful shutdown.
    
    Handles SIGINT (Ctrl+C) and SIGTERM to allow campaigns to complete
    current injection and cleanup properly before exit.
    
    Must be called before campaign execution begins.
    """
    def signal_handler(signum, frame):
        """Handle interrupt signals by requesting graceful stop."""
        global _active_controller
        
        # Determine signal name for logging
        sig_name = "SIGINT" if signum == signal.SIGINT else f"signal {signum}"
        
        if _active_controller is not None:
            # Request graceful stop - let time profile finish current injection
            print(f"\n{sig_name} received - requesting graceful shutdown...")
            _active_controller.request_stop()
            _active_controller.set_termination_reason("User interrupt")
        else:
            # Controller not yet created - exit immediately
            print(f"\n{sig_name} received during initialization - aborting...")
            sys.exit(130)
    
    # Register handlers for both SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def register_controller(controller):
    """
    Register controller for signal handling.
    
    Must be called after controller creation to enable graceful shutdown.
    
    Args:
        controller: InjectionController instance
    """
    global _active_controller
    _active_controller = controller


def clear_controller():
    """
    Clear controller reference.
    
    Should be called in cleanup/finally block.
    """
    global _active_controller
    _active_controller = None