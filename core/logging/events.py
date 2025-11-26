# =============================================================================
# FATORI-V • FI Logging Events
# File: log/events.py
# -----------------------------------------------------------------------------
# Core logging functions for all FI campaign events.
#=============================================================================

from typing import List, Dict, Optional, Any
import sys

from fi import fi_settings
from fi.core.logging import log_levels
from fi.core.logging import message_formats


# -----------------------------------------------------------------------------
# Module state
# -----------------------------------------------------------------------------

# File handle for the log file (opened by setup_log_file)
_log_file_handle = None

# Config object for accessing runtime settings
# Set by configure_logging() at campaign startup
_log_config = None


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

def configure_logging(cfg):
    """
    Configure logging system with Config object.
    
    This allows logging functions to access runtime configuration
    instead of relying solely on fi_settings defaults.
    
    Args:
        cfg: Config object with logging settings
    """
    global _log_config
    _log_config = cfg


def _get_log_level() -> str:
    """
    Get current log level from Config or fi_settings.
    
    Returns:
        Log level string ("minimal", "normal", or "verbose")
    """
    if _log_config is not None and hasattr(_log_config, 'log_level'):
        return _log_config.log_level
    return getattr(fi_settings, 'LOG_LEVEL', 'normal')


def _should_log_event(event_name: str):
    """
    Check if an event should be logged at the current level.
    
    Uses log_levels.py to determine console/file settings based on
    the current LOG_LEVEL.
    
    Args:
        event_name: Name of the event (e.g., 'injection', 'error')
        
    Returns:
        Tuple of (to_console: bool, to_file: bool)
    """
    level = _get_log_level()
    return log_levels.should_log_event(event_name, level)


# -----------------------------------------------------------------------------
# File management
# -----------------------------------------------------------------------------

def setup_log_file(log_root: str, log_filename: str):
    """
    Open the log file for writing.
    
    Creates the log directory if it doesn't exist, then opens the log file
    in append mode. This allows multiple campaigns to write to the same file
    if desired.
    
    Args:
        log_root: Directory path where log file should be created
        log_filename: Name of the log file (no path, just filename)
    """
    global _log_file_handle
    
    from pathlib import Path
    
    # Resolve log directory
    log_dir = Path(log_root)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Open log file in append mode
    log_path = log_dir / log_filename
    _log_file_handle = open(log_path, 'a', encoding='utf-8')
    
    # Write header to separate campaigns in log file
    _write_log_header()


def close_log_file():
    """
    Close the log file handle.
    
    Should be called at campaign end or in cleanup to ensure all writes
    are flushed to disk.
    """
    global _log_file_handle
    
    if _log_file_handle is not None:
        _log_file_handle.close()
        _log_file_handle = None


def _write_log_header():
    """
    Write session header to log file.
    
    This helps separate different campaign runs in the same log file,
    showing when each campaign started.
    """
    import datetime
    
    if _log_file_handle is None:
        return
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 78
    
    _log_file_handle.write(f"\n{separator}\n")
    _log_file_handle.write(f"CAMPAIGN SESSION STARTED: {timestamp}\n")
    _log_file_handle.write(f"{separator}\n\n")
    _log_file_handle.flush()


# -----------------------------------------------------------------------------
# Core write functions
# -----------------------------------------------------------------------------

def _write_to_file(msg: str):
    """Write message to log file."""
    if _log_file_handle is not None:
        _log_file_handle.write(msg + "\n")
        _log_file_handle.flush()


def _write_to_console(msg: str):
    """Write message to console (stdout)."""
    print(msg)
    sys.stdout.flush()


# -----------------------------------------------------------------------------
# Campaign lifecycle events
# -----------------------------------------------------------------------------

def log_startup(config):
    """
    Log campaign startup information.
    
    This is called at the beginning of a campaign to record the configuration
    being used. It creates the campaign header in the log.
    
    Args:
        config: Config object with campaign settings
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('campaign_header')
    if not to_console and not to_file:
        return
    
    # Format campaign header message
    msg = message_formats.format_campaign_header(config)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


def log_campaign_end(stats: Dict[str, int]):
    """
    Log campaign completion.
    
    Called at the end of a campaign to record final statistics and mark
    the end of the session.
    
    Args:
        stats: Dictionary with campaign statistics (total, successes, failures)
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('campaign_footer')
    if not to_console and not to_file:
        return
    
    # Format campaign end message
    msg = message_formats.format_campaign_end(stats)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


# -----------------------------------------------------------------------------
# System initialization events
# -----------------------------------------------------------------------------

def log_systemdict_loaded(path: str, boards: List[str], total_modules: int):
    """
    Log system dictionary loading.
    
    Records that the system dictionary was successfully loaded and what
    boards and modules were found.
    
    Args:
        path: Path to the system dictionary file
        boards: List of board names found in the dictionary
        total_modules: Total number of modules defined
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('systemdict_load')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_systemdict_load(path, boards, total_modules)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


def log_board_resolved(board_name: str, source: str):
    """
    Log board name resolution.
    
    Records which board name was selected and where it came from
    (CLI, system dict, or default).
    
    Args:
        board_name: The resolved board name
        source: Where the board name came from
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('board_resolution')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_board_resolution(board_name, source)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


# -----------------------------------------------------------------------------
# ACME / pool building events
# -----------------------------------------------------------------------------

def log_acme_expansion(region: str, count: int):
    """
    Log ACME region expansion.
    
    Records when ACME expands a region specification to actual configuration
    bit addresses. Shows how many bits were found for the region.
    
    Args:
        region: Region specification (e.g., "SLICE_X0Y0:SLICE_X10Y10")
        count: Number of configuration bits found in region
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('acme_expansion')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_acme_expansion(region, count)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


def log_acme_cache_hit(region: str, count: int):
    """
    Log ACME cache hit.
    
    Records when ACME finds a region expansion in its cache, avoiding
    the need to re-expand the region.
    
    Args:
        region: Region specification
        count: Number of cached configuration bits
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('acme_cache_hit')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_acme_cache_hit(region, count)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


def log_pool_built(stats: Dict, profile_name: str):
    """
    Log pool building completion.
    
    Records that the target pool was successfully built by an area profile,
    showing statistics about what was included.
    
    Args:
        stats: Dictionary with pool statistics
        profile_name: Name of the area profile that built the pool
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('pool_built')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_pool_built(stats, profile_name)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


# -----------------------------------------------------------------------------
# Injection events (high frequency)
# -----------------------------------------------------------------------------

def log_injection(target, success: bool, timestamp: float = None):
    """
    Log individual injection event.
    
    Records each injection attempt with the target specification and whether
    it succeeded or failed. This is a high-frequency event (one per injection).
    
    Args:
        target: TargetSpec being injected
        success: Whether injection succeeded
        timestamp: Optional timestamp for the injection
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('injection')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_injection(target, success)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


# -----------------------------------------------------------------------------
# Campaign summary
# -----------------------------------------------------------------------------

def log_campaign_summary(total: int, successes: int, failures: int):
    """
    Log campaign summary statistics.
    
    Shows aggregate injection results at the end of a campaign.
    
    Args:
        total: Total number of injections attempted
        successes: Number of successful injections
        failures: Number of failed injections
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('campaign_summary')
    if not to_console and not to_file:
        return
    
    # Format message
    msg = message_formats.format_campaign_summary(total, successes, failures)
    
    # Write to destinations
    if to_file:
        _write_to_file(msg)
    if to_console:
        _write_to_console(msg)


# -----------------------------------------------------------------------------
# Error logging
# -----------------------------------------------------------------------------

def log_error(msg: str, exc: Exception = None):
    """
    Log error event.
    
    Records errors that occur during campaign execution. Errors are always
    important and should be visible.
    
    Args:
        msg: Error message describing what went wrong
        exc: Optional exception object with additional details
    """
    # Check if event should be logged at current level
    to_console, to_file = _should_log_event('error')
    if not to_console and not to_file:
        return
    
    # Format error message
    error_msg = message_formats.format_error(msg, exc)
    
    # Write to destinations
    if to_file:
        _write_to_file(error_msg)
    if to_console:
        _write_to_console(error_msg)


# -----------------------------------------------------------------------------
# SEM command logging (high frequency)
# -----------------------------------------------------------------------------

def log_sem_command(command: str, response: List[str]):
    """
    Log SEM protocol command and response.
    
    Records both the command sent to SEM and all response lines received.
    This is a high-frequency event (one per SEM command).
    
    Args:
        command: SEM command sent (e.g., "I", "N C000A098000", "S")
        response: List of response lines from SEM
    """
    # Check if SEM command logging is enabled at current level
    cmd_console, cmd_file = _should_log_event('sem_command')
    if cmd_console or cmd_file:
        cmd_msg = message_formats.format_sem_command(command)
        
        if cmd_file:
            _write_to_file(cmd_msg)
        if cmd_console:
            _write_to_console(cmd_msg)
    
    # Check if SEM response logging is enabled at current level
    resp_console, resp_file = _should_log_event('sem_response')
    if resp_console or resp_file:
        for line in response:
            resp_msg = message_formats.format_sem_response(line)
            
            if resp_file:
                _write_to_file(resp_msg)
            if resp_console:
                _write_to_console(resp_msg)