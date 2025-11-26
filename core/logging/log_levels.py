# =============================================================================
# FATORI-V • FI Logging Levels Configuration
# File: config/log_levels.py
# -----------------------------------------------------------------------------
# Defines what gets logged at each verbosity level (minimal/normal/verbose).
#
# CUSTOMIZATION:
# Edit this file to control which events appear at each level.
# Simply move event tuples between the three lists to adjust logging.
#
# Each tuple is: (event_name, to_console, to_file)
#   - event_name: Internal name for the event (matches log function)
#   - to_console: True = print to console, False = suppress from console
#   - to_file: True = write to log file, False = suppress from file
#
# USAGE:
# Set via CLI: --log-level minimal|normal|verbose
# Or edit fi_settings.py: LOG_LEVEL = "minimal|normal|verbose"
#=============================================================================


# =============================================================================
# MINIMAL - Only Critical Information
# =============================================================================
#
# Use for production runs where you only want to know:
#   - Campaign started/completed
#   - Errors that occurred
#   - Final summary
#
# Console: Clean and quiet
# File: Minimal record of campaign lifecycle
# =============================================================================

MINIMAL = [
    # Campaign lifecycle - know when it starts/ends
    ('campaign_header', True, True),
    ('campaign_footer', True, True),
    ('campaign_summary', True, True),
    
    # Errors - always need to see these
    ('error', True, True),
]


# =============================================================================
# NORMAL - Standard Operation (Default)
# =============================================================================
#
# Use for typical development/testing where you want:
#   - Campaign lifecycle and summary
#   - System initialization steps
#   - Pool building results
#   - Errors
#   - BUT NOT individual injections (too noisy)
#
# Console: Shows major steps and progress
# File: Complete record except some high-frequency details
# =============================================================================

NORMAL = [
    # Campaign lifecycle
    ('campaign_header', True, True),
    ('campaign_footer', True, True),
    ('campaign_summary', True, True),
    
    # System initialization - good to see what was loaded
    ('systemdict_load', True, True),
    ('board_resolution', True, True),
    ('sem_preflight', True, True),
    
    # Pool building - important to verify target selection
    ('pool_built', True, True),
    ('acme_expansion', True, True),
    
    # High-frequency events - file only (too noisy for console)
    ('acme_cache_hit', False, True),  # File only - performance info
    ('injection', False, True),        # File only - one per injection
    ('sem_command', False, True),      # File only - high frequency
    ('sem_response', False, True),     # File only - high frequency
    
    # Errors - always visible
    ('error', True, True),
]


# =============================================================================
# VERBOSE - Everything (Debug Mode)
# =============================================================================
#
# Use for debugging when you need to see:
#   - Everything that happens
#   - Individual injections in real-time
#   - Every SEM command and response
#   - ACME cache behavior
#
# Console: Very noisy, shows all activity
# File: Complete record of every event
# =============================================================================

VERBOSE = [
    # Campaign lifecycle
    ('campaign_header', True, True),
    ('campaign_footer', True, True),
    ('campaign_summary', True, True),
    
    # System initialization
    ('systemdict_load', True, True),
    ('board_resolution', True, True),
    ('sem_preflight', True, True),
    
    # Pool building
    ('pool_built', True, True),
    ('acme_expansion', True, True),
    ('acme_cache_hit', True, True),  # Now visible on console
    
    # High-frequency events - all visible
    ('injection', True, True),        # See every injection happen
    ('sem_command', True, True),      # See every SEM command
    ('sem_response', True, True),     # See every SEM response
    
    # Errors
    ('error', True, True),
]


# =============================================================================
# Helper Functions
# =============================================================================

def get_level_config(level: str):
    """
    Get the logging configuration for a given level.
    
    Args:
        level: One of "minimal", "normal", or "verbose"
        
    Returns:
        List of (event_name, to_console, to_file) tuples
        Falls back to NORMAL if level is unknown
    """
    level = level.lower()
    
    if level == "minimal":
        return MINIMAL
    elif level == "verbose":
        return VERBOSE
    else:
        # Default to NORMAL for unknown levels
        return NORMAL


def should_log_event(event_name: str, level: str):
    """
    Check if an event should be logged at the given level.
    
    Args:
        event_name: Name of the event (e.g., 'injection', 'error')
        level: Current log level ("minimal", "normal", or "verbose")
        
    Returns:
        Tuple of (to_console: bool, to_file: bool)
        Returns (False, False) if event not found at this level
    """
    config = get_level_config(level)
    
    for name, to_console, to_file in config:
        if name == event_name:
            return (to_console, to_file)
    
    # Event not in current level - don't log
    return (False, False)


def get_all_events():
    """
    Get a list of all known event names across all levels.
    
    Useful for validation and documentation.
    
    Returns:
        Set of event name strings
    """
    events = set()
    for config in [MINIMAL, NORMAL, VERBOSE]:
        for name, _, _ in config:
            events.add(name)
    return events