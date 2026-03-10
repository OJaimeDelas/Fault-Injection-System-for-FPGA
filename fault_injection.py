# =============================================================================
# FATORI-V • FI Console
# File: fault_injection.py
# -----------------------------------------------------------------------------
# Main entry point for fault injection campaigns.
#
# This script orchestrates the FI campaign flow per thesis Chapter 6.2.2:
#   1. Configuration: CLI parsing, logging, SystemDict, board resolution, profiles
#   2. Target Pool Build: ACME expansion with caching, EBD waiting
#   3. Transport Activation: Backend initialization based on pool analysis
#   4. Synchronization: Wait for benchmark ready signal (if enabled)
#   5. Execution: Time Profile consumes Target Pool
#   6. Outputs: Cleanup and resource management
# =============================================================================

import sys
from pathlib import Path
from typing import Optional
import logging

# Make script runnable from within fi/ directory
script_path = Path(__file__).resolve()
fi_package_dir = script_path.parent
parent_dir = fi_package_dir.parent

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

# EBD waiting
from fi.core.campaign.ebd_waiter import wait_for_ebd_file

# Injection
from fi.core.campaign.controller import create_injection_controller
from fi.backend.reg_inject.board_interface import create_board_interface

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
    
    Campaign flow per thesis Chapter 6.2.2:
      1. Configuration: CLI, logging, SystemDict, board resolution, profiles
      2. Target Pool Build: EBD wait, ACME expansion with caching
      3. Transport Activation: Analyze pool, initialize backends
      4. Synchronization: Wait for benchmark ready signal
      5. Execution: Time Profile consumes Target Pool
      6. Outputs: Cleanup resources
    
    Graceful shutdown:
      - SIGINT (Ctrl+C) and SIGTERM caught via signal handlers
      - Controller notified to stop gracefully
      - Time profile completes current injection before exiting
      - All files flushed and closed properly
      - Campaign stats logged with termination reason
    
    Args:
        argv: Command-line arguments (for testing, defaults to sys.argv)
    
    Returns:
        Exit code (0 = success, 1 = error, 130 = interrupted)
    """
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Initialize resource handles for cleanup
    transport = None
    log_ctx = None
    controller = None
    
    try:
        # =====================================================================
        # PHASE 1: CONFIGURATION
        # =====================================================================
        
        # Parse CLI and build config
        args = parse_args(argv)
        cfg = build_config(args)
        
        # Setup logging
        log_ctx = setup_logging(cfg)
        log_startup(cfg)
        
        # Load SystemDict
        system_dict = load_system_dict(cfg.system_dict_path, cfg.system_dict_is_user_path)
        
        # Resolve board name
        board_name = resolve_board_name(cfg, system_dict)
        log_board_resolved(board_name, source="resolved")
        
        # Load area and time profiles
        area_profile = load_area_profile(cfg)
        time_profile = load_time_profile(cfg)
        
        # =====================================================================
        # PHASE 2: EBD WAIT (ensures FPGA is loading before SEM preflight)
        # =====================================================================
        
        # Wait for EBD file if needed (blocking)
        # EBD appearance signals that FPGA bitstream generation is complete
        # This ensures SEM IP will be available shortly for preflight test
        if cfg.ebd_path:
            logger.info(f"Waiting for EBD file at: {cfg.ebd_path}")
            if not wait_for_ebd_file(cfg.ebd_path, timeout_s=None):
                logger.error("EBD file did not appear - aborting campaign")
                return 1
            logger.info("EBD file ready - FPGA loading in progress")
        
        # =====================================================================
        # PHASE 3: TRANSPORT ACTIVATION & SEM PREFLIGHT
        # =====================================================================
        
        # Open UART transport and run SEM preflight test
        # EBD wait completed, so FPGA should be booting and SEM IP initializing
        # Preflight validates hardware connection before pool building
        logger.info("Opening UART transport for SEM preflight")
        preflight_success = False
        try:
            transport, sem_proto_initial = open_sem(cfg, log_ctx)
            preflight_success = True
        except RuntimeError as e:
            # SEM preflight failed - log and abort gracefully
            logger.error(f"Campaign aborted: {e}")
            log_campaign_end({'total': 0, 'successes': 0, 'failures': 0}, 'preflight_failed')
            return 1
        
        # =====================================================================
        # PHASE 4: TARGET POOL BUILD
        # =====================================================================
        
        # Build TargetPool (ACME expansion with caching happens inside)
        target_pool = build_campaign_pool(
            area_profile=area_profile,
            system_dict=system_dict,
            board_name=board_name,
            ebd_path=cfg.ebd_path,
            cfg=cfg
        )
        
        # =====================================================================
        # PHASE 5: BACKEND INITIALIZATION
        # =====================================================================
        
        # Analyze pool to determine backend requirements
        backend_reqs = target_pool.get_backend_requirements()
        logger.info(f"Backend requirements: SEM={backend_reqs['sem']}, REG_INJECT={backend_reqs['reg_inject']}")
        
        # Initialize SEM backend for CONFIG targets (reuse transport from preflight)
        sem_proto = None
        if backend_reqs["sem"]:
            logger.info("Initializing SEM backend (CONFIG targets detected)")
            sem_proto = sem_proto_initial  # Reuse protocol from preflight
        else:
            logger.info("Skipping SEM backend (no CONFIG targets)")
            # Transport was opened for preflight but not needed - keep it open for reg_inject
        
        # Initialize register injection backend for REG targets
        board_if = None
        if backend_reqs["reg_inject"]:
            if cfg.reg_inject_force_disabled:
                logger.info("Register injection disabled by --reg-inject-disabled flag")
            else:
                logger.info("Initializing register injection backend (REG targets detected)")
            board_if = create_board_interface(cfg, transport=transport)
        else:
            logger.info("Skipping register injection backend (no REG targets)")
        
        # =====================================================================
        # PHASE 4: SYNCHRONIZATION
        # =====================================================================
        
        # Setup benchmark synchronization (if enabled)
        # This happens AFTER everything is ready to inject
        benchmark_sync = None
        if cfg.benchmark_sync_enabled:
            benchmark_sync = BenchmarkSync(
                sync_file_path=cfg.benchmark_sync_file,
                check_interval_s=cfg.benchmark_check_interval_s,
                check_every_n=cfg.benchmark_check_every_n
            )
            
            # Wait for benchmark to signal ready (blocking)
            logger.info("Benchmark synchronization enabled")
            logger.info("Waiting for benchmark to write READY to sync file")
            if not benchmark_sync.wait_for_benchmark_ready(
                timeout_s=cfg.benchmark_sync_timeout
            ):
                logger.error("Benchmark did not signal ready - aborting campaign")
                return 1
            logger.info("Benchmark ready - starting injection campaign")
        
        # =====================================================================
        # PHASE 5: EXECUTION
        # =====================================================================
        
        # Create injection controller with backends
        controller = create_injection_controller(
            sem_proto=sem_proto,
            target_pool=target_pool,
            board_if=board_if,
            log_ctx=log_ctx,
            benchmark_sync=benchmark_sync
        )
        
        # Register controller for signal handlers
        register_controller(controller)
        
        # Run campaign - Time Profile consumes Target Pool
        time_profile.run(controller)
        
        # =====================================================================
        # PHASE 6: OUTPUTS
        # =====================================================================
        
        # Log campaign completion
        stats = controller.get_stats()
        termination_reason = stats.get('termination_reason', 'completed')
        log_campaign_end(stats, termination_reason)
        
        return 0
    
    except KeyboardInterrupt:
        # Signal handler set termination reason and requested stop
        # Log campaign stats if controller was created
        if controller is not None:
            try:
                stats = controller.get_stats()
                termination_reason = stats.get('termination_reason', 'User interrupt')
                log_campaign_end(stats, termination_reason)
            except Exception:
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
        # Cleanup resources (always runs)
        cleanup_resources(transport, log_ctx)


if __name__ == "__main__":
    sys.exit(main())