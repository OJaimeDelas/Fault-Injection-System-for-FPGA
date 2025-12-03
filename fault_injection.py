# =============================================================================
# FATORI-V • FI Console
# File: fault_injection.py
# -----------------------------------------------------------------------------
# Main entry point for fault injection campaigns.
#
# This script orchestrates the entire FI campaign flow:
#   1. Parse CLI and build config
#   2. Setup logging
#   3. Load SystemDict
#   4. Resolve board name
#   5. Load area and time profiles
#   6. Setup benchmark synchronization (if enabled)
#   7. Build TargetPool
#   8. Analyze pool to determine backend requirements
#   9. Initialize backends conditionally (SEM, GPIO)
#  10. Create controller
#  11. Run campaign
#  12. Cleanup
#=============================================================================

import sys
from pathlib import Path
from typing import Optional
import logging

# Make script runnable from within fi/ directory
# Detect if we're inside the fi package and add parent to path
script_path = Path(__file__).resolve()
fi_package_dir = script_path.parent  # The fi/ directory
parent_dir = fi_package_dir.parent   # The directory containing fi/

# If 'fi' package directory exists as sibling, we're in the right structure
if (parent_dir / 'fi').is_dir() and parent_dir not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(parent_dir))

# CLI and config
from fi.core.config.cli_parser import parse_args
from fi.core.config.config import build_config

# Setup
from fi.core.logging.setup import setup_logging
from fi.backend.sem.setup import open_sem
from fi.core.campaign.board_resolution import resolve_board_name

# Data loading
from fi.targets.dict_loader import load_system_dict

# Profiles
from fi.profiles.area.common.loader import load_area_profile
from fi.profiles.time.common.loader import load_time_profile
from fi.core.campaign.pool_builder import build_campaign_pool

# Injection
from fi.core.campaign.controller import create_injection_controller
from fi.backend.gpio.board_interface import create_board_interface

# Synchronization
from fi.core.campaign.sync import BenchmarkSync

# Signal handling
from fi.core.campaign.signal_handler import setup_signal_handlers, register_controller, clear_controller

# Cleanup
from fi.core.campaign.cleanup import cleanup_resources

# Logging
from fi.core.logging.events import log_board_resolved, log_campaign_end, log_startup

logger = logging.getLogger(__name__)


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for FI console.
    
    High-level campaign flow:
      1. Setup signal handlers for graceful shutdown
      2. Parse CLI and build config
      3. Setup logging
      4. Load SystemDict
      5. Resolve board name
      6. Load area and time profiles
      7. Setup benchmark synchronization (if enabled)
      8. Build TargetPool
      9. Analyze pool to determine backend requirements
     10. Initialize backends conditionally (SEM, GPIO)
     11. Create controller
     12. Run campaign
     13. Cleanup
    
    Graceful shutdown:
      - SIGINT (Ctrl+C) and SIGTERM are caught via signal handlers
      - Controller is notified to stop gracefully
      - Time profile completes current injection before exiting
      - All files are flushed and closed properly
      - Campaign stats are logged with termination reason
    
    Args:
        argv: Command-line arguments (for testing, defaults to sys.argv)
    
    Returns:
        Exit code (0 = success, 1 = error, 130 = interrupted)
    """
    # 1. Setup signal handlers for graceful shutdown
    # This must happen before any campaign execution begins
    setup_signal_handlers()
    
    # 2. Parse CLI and build config
    args = parse_args(argv)
    cfg = build_config(args)
    
    # Initialize resource handles for cleanup
    transport = None
    log_ctx = None
    controller = None  # Track controller for cleanup
    
    try:
        # 2. Setup logging
        log_ctx = setup_logging(cfg)
        log_startup(cfg)  # Log campaign header
        
        # 3. Load SystemDict
        system_dict = load_system_dict(cfg.system_dict_path, cfg.system_dict_is_user_path)
        
        # 4. Resolve board name
        board_name = resolve_board_name(cfg, system_dict)
        log_board_resolved(board_name, source="resolved")
        
        # 5. Load area and time profiles
        area_profile = load_area_profile(cfg)
        time_profile = load_time_profile(cfg)
        
        # 6. Setup benchmark synchronization (if enabled)
        benchmark_sync = None
        if cfg.benchmark_sync_enabled:
            benchmark_sync = BenchmarkSync(
                sync_file_path=cfg.benchmark_sync_file,
                check_interval_s=cfg.benchmark_check_interval_s,
                check_every_n=cfg.benchmark_check_every_n
            )
            
            # Wait for benchmark to signal ready (blocking)
            logger.info("Benchmark synchronization enabled")
            if not benchmark_sync.wait_for_benchmark_ready(
                timeout_s=cfg.benchmark_sync_timeout
            ):
                logger.error("Benchmark did not signal ready - aborting campaign")
                return 1
        
        # 7. Build TargetPool
        target_pool = build_campaign_pool(
            area_profile=area_profile,
            system_dict=system_dict,
            board_name=board_name,
            ebd_path=cfg.ebd_path,
            cfg=cfg  # Pass config for TargetPool export
        )
        
        # 8. Analyze pool to determine backend requirements
        backend_reqs = target_pool.get_backend_requirements()
        logger.info(f"Backend requirements: SEM={backend_reqs['sem']}, GPIO={backend_reqs['gpio']}")
        
        # 9. Initialize backends conditionally based on pool analysis
        
        # Open transport if either SEM or GPIO backends are needed
        # Both backends share the same UART connection
        transport = None
        if backend_reqs["sem"] or backend_reqs["gpio"]:
            logger.info("Opening UART transport for injection backends")
            transport, _ = open_sem(cfg, log_ctx)
        
        # SEM backend (for CONFIG targets)
        sem_proto = None
        if backend_reqs["sem"]:
            logger.info("Initializing SEM backend (CONFIG targets detected in pool)")
            # Reuse opened transport to create protocol wrapper
            from fi.backend.sem.protocol import SemProtocol
            sem_proto = SemProtocol(tr=transport)
        else:
            logger.info("Skipping SEM initialization (no CONFIG targets in pool)")
        
        # GPIO backend (for REG targets)
        board_if = None
        if backend_reqs["gpio"]:
            if cfg.gpio_force_disabled:
                logger.info("GPIO force-disabled by --gpio-disabled flag (REG targets will use NoOp)")
            else:
                logger.info("Initializing GPIO backend (REG targets detected in pool)")
            # Pass transport to board interface factory
            board_if = create_board_interface(cfg, transport=transport)
        else:
            logger.info("Skipping GPIO initialization (no REG targets in pool)")
        
        # 10. Create injection controller with backends (may be None)
        controller = create_injection_controller(
            sem_proto=sem_proto,  # None if no CONFIG targets
            target_pool=target_pool,
            board_if=board_if,    # None if no REG targets
            log_ctx=log_ctx,
            benchmark_sync=benchmark_sync
        )

        # Register controller for signal handlers
        register_controller(controller)
        
        # 11. Run campaign
        time_profile.run(controller)

        # Log campaign completion with termination reason
        stats = controller.get_stats()
        termination_reason = stats.get('termination_reason', 'unknown')
        log_campaign_end(stats, termination_reason)
        
        return 0
    
    except KeyboardInterrupt:
        # Signal handler already set termination reason and requested stop
        # Time profile should have exited gracefully
        # Log campaign stats if controller was created
        if controller is not None:
            try:
                stats = controller.get_stats()
                termination_reason = stats.get('termination_reason', 'User interrupt')
                log_campaign_end(stats, termination_reason)
            except Exception:
                # If logging fails, don't crash - cleanup will still happen
                pass
        return 130
    
    except Exception as exc:
        # Fatal error during campaign
        print(f"\nFATAL ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Clear controller reference from signal handler
        clear_controller()
        # 12. Cleanup resources (always runs)
        cleanup_resources(transport, log_ctx)


if __name__ == "__main__":
    sys.exit(main())