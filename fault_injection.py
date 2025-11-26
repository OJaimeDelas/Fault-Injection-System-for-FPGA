# =============================================================================
# FATORI-V • FI Console
# File: fault_injection.py
# -----------------------------------------------------------------------------
# Main entry point for fault injection campaigns.
#
# This script orchestrates the entire FI campaign flow:
#   1. Parse CLI and build config
#   2. Setup logging
#   3. Setup SEM connection
#   4. Load SystemDict
#   5. Resolve board name
#   6. Load area and time profiles
#   7. Build TargetPool
#   8. Create controller
#   9. Run campaign
#  10. Cleanup
#=============================================================================

import sys
from pathlib import Path
from typing import Optional

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

# Cleanup
from fi.core.campaign.cleanup import cleanup_resources

# Logging
from fi.core.logging.events import log_board_resolved, log_campaign_end, log_startup


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for FI console.
    
    High-level campaign flow:
      1. Parse CLI and build config
      2. Setup logging
      3. Setup SEM connection
      4. Load SystemDict
      5. Resolve board name
      6. Load area and time profiles
      7. Build TargetPool
      8. Create controller
      9. Run campaign
     10. Cleanup
    
    Args:
        argv: Command-line arguments (for testing, defaults to sys.argv)
    
    Returns:
        Exit code (0 = success, 1 = error, 130 = interrupted)
    """
    
    # 1. Parse CLI and build config
    args = parse_args(argv)
    cfg = build_config(args)
    
    # Initialize resource handles for cleanup
    transport = None
    log_ctx = None
    
    try:
        # 2. Setup logging
        log_ctx = setup_logging(cfg)
        log_startup(cfg)  # Log campaign header
        
        # 3. Setup SEM connection
        transport, proto = open_sem(cfg, log_ctx)
        
        # 4. Load SystemDict
        system_dict = load_system_dict(cfg.system_dict_path)
        
        # 5. Resolve board name
        board_name = resolve_board_name(cfg, system_dict)
        log_board_resolved(board_name, source="resolved")
        
        # 6. Load area and time profiles
        area_profile = load_area_profile(cfg)
        time_profile = load_time_profile(cfg)
        
        # 7. Build TargetPool
        target_pool = build_campaign_pool(
            area_profile=area_profile,
            system_dict=system_dict,
            board_name=board_name,
            ebd_path=cfg.ebd_path
        )
        
        # 8. Create injection controller
        board_if = create_board_interface(cfg)
        controller = create_injection_controller(
            sem_proto=proto,
            target_pool=target_pool,
            board_if=board_if,
            log_ctx=log_ctx
        )
        
        # 9. Run campaign
        time_profile.run(controller)

        # Log campaign completion
        stats = controller.get_stats()
        log_campaign_end(stats)
        
        return 0
    
    except KeyboardInterrupt:
        # User interrupted with Ctrl+C
        print("\nCampaign interrupted by user.")
        return 130
    
    except Exception as exc:
        # Fatal error during campaign
        print(f"\nFATAL ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # 10. Cleanup resources (always runs)
        cleanup_resources(transport, log_ctx)


if __name__ == "__main__":
    sys.exit(main())