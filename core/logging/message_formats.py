# =============================================================================
# FATORI-V • FI Logging Message Formats
# File: log/message_formats.py
# -----------------------------------------------------------------------------
# Centralized message formatting for all console and log output.
#=============================================================================

from typing import Dict, Any, List
from fi.console import console_settings as cs
from fi.console import console_styling as sty


def format_log_header(timestamp: str) -> str:
    """
    Format the log file header.
    
    Args:
        timestamp: Timestamp string for when log was started
    
    Returns:
        Formatted header string
    """
    sep = sty.make_section_separator()
    return (
        sep + "\n" +
        "FATORI-V FI Console - Injection Log\n" +
        f"Started: {timestamp}\n" +
        sep
    )


def format_campaign_header(config: Any) -> str:
    """
    Format the campaign startup banner.
    
    Args:
        config: Config object with campaign parameters
    
    Returns:
        Formatted campaign header string
    """
    from fi.core.config.seed_manager import format_seed_source, derive_area_seed, derive_time_seed
    
    # Format seed information
    if config.global_seed is not None:
        global_seed_str = f"{config.global_seed}"
    else:
        global_seed_str = "not set"
    
    # Calculate effective seeds for display
    if config.area_seed is not None:
        effective_area_seed = config.area_seed
    elif config.global_seed is not None:
        effective_area_seed = derive_area_seed(config.global_seed)
    else:
        effective_area_seed = None
    
    if config.time_seed is not None:
        effective_time_seed = config.time_seed
    elif config.global_seed is not None:
        effective_time_seed = derive_time_seed(config.global_seed)
    else:
        effective_time_seed = None
    
    area_seed_str = format_seed_source(
        config.area_seed,
        config.global_seed,
        effective_area_seed
    )
    
    time_seed_str = format_seed_source(
        config.time_seed,
        config.global_seed,
        effective_time_seed
    )
    
    sep = sty.make_section_separator()
    return (
        "\n" + sep + "\n" +
        "Campaign Configuration:\n" +
        f"  Device: {config.dev} @ {config.baud} baud\n" +
        f"  Area Profile: {config.area_profile}\n" +
        f"  Time Profile: {config.time_profile}\n" +
        f"  Global Seed: {global_seed_str}\n" +
        f"  Area Seed: {area_seed_str}\n" +
        f"  Time Seed: {time_seed_str}\n" +
        sep
    )


def format_campaign_end(stats: Dict[str, int]) -> str:
    """
    Format the campaign completion banner.
    
    Args:
        stats: Dictionary with 'total', 'successes', 'failures' keys
    
    Returns:
        Formatted campaign footer string
    """
    sep = sty.make_section_separator()
    return (
        "\n" + sep + "\n" +
        "Campaign Complete:\n" +
        f"  Total injections: {stats['total']}\n" +
        f"  Successes: {stats['successes']}\n" +
        f"  Failures: {stats['failures']}\n" +
        sep
    )


def format_pool_built(stats: Dict, profile_name: str) -> str:
    """
    Format the pool building result message.
    
    Args:
        stats: Pool statistics dictionary
        profile_name: Name of the area profile that built the pool
    
    Returns:
        Formatted pool built message
    """
    total = stats['total']
    by_kind = stats['by_kind']
    by_module = stats.get('by_module', {})
    
    lines = [
        f"[Pool] Built by '{profile_name}': {total} targets",
        f"       By kind: {by_kind}"
    ]
    
    # Add per-module breakdown if available
    if by_module:
        for module, counts in sorted(by_module.items()):
            lines.append(f"       {module}: {counts}")
    
    return "\n".join(lines)


def format_injection(target: Any, success: bool) -> str:
    """
    Format an individual injection message.
    
    Args:
        target: TargetSpec that was injected
        success: Whether injection succeeded
    
    Returns:
        Formatted injection message
    """
    kind = target.kind.value
    module = target.module_name
    status = "OK" if success else "FAIL"
    
    if kind == "CONFIG":
        addr = target.config_address
        return f"[Inject] {module}/{kind}: {addr} → {status}"
    else:  # REG
        reg_id = target.reg_id
        return f"[Inject] {module}/{kind}: reg_id={reg_id} → {status}"


def format_sem_command(command: str) -> str:
    """
    Format a SEM command being sent.
    
    Args:
        command: Command string sent to SEM
    
    Returns:
        Formatted SEM command message
    """
    return f"[SEM] > {command}"


def format_sem_response(line: str) -> str:
    """
    Format a SEM response line received.
    
    Args:
        line: Response line from SEM
    
    Returns:
        Formatted SEM response message
    """
    return f"[SEM] < {line}"


def format_acme_expansion(region: str, count: int) -> str:
    """
    Format ACME expansion result message.
    
    Args:
        region: Clock region that was expanded
        count: Number of config bits generated
    
    Returns:
        Formatted ACME expansion message
    """
    return f"[ACME] Expanded {region} → {count} config bits"


def format_board_resolution(board_name: str, source: str) -> str:
    """
    Format board resolution message.
    
    Args:
        board_name: Resolved board name
        source: How the board was resolved (e.g., 'CLI', 'resolved')
    
    Returns:
        Formatted board resolution message
    """
    return f"[Board] Resolved to '{board_name}' (source: {source})"


def format_systemdict_load(path: str, boards: list, total_modules: int) -> str:
    """
    Format system dictionary loaded message.
    
    Args:
        path: Path to system dict file
        boards: List of board names loaded
        total_modules: Total number of modules across all boards
    
    Returns:
        Formatted systemdict loaded message
    """
    board_count = len(boards)
    return f"[SystemDict] Loaded from {path}: {board_count} boards, {total_modules} modules"


def format_error(msg: str, exc: Exception = None) -> str:
    """
    Format an error message.
    
    Args:
        msg: Error message text
        exc: Optional exception object
    
    Returns:
        Formatted error message
    """
    error_msg = f"[ERROR] {msg}"
    if exc:
        error_msg += f": {exc}"
    return error_msg