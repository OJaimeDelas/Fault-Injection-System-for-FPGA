# =============================================================================
# FATORI-V • FI Logging Message Formats
# File: log/message_formats.py
# -----------------------------------------------------------------------------
# Centralized message formatting for all console and log output.
#=============================================================================

from typing import Dict, Any, List
from fi.console import console_settings as cs
from fi.console import console_styling as sty


def format_acme_cache_hit(region: str, count: int) -> str:
    """
    Format ACME cache hit message.
    
    Args:
        region: Region that was loaded from cache
        count: Number of cached config bits
    
    Returns:
        Formatted ACME cache hit message
    """
    return f"[ACME] Cache hit: Loaded {count} addresses from {region}"


def format_sync_waiting(sync_file: str) -> str:
    """
    Format benchmark sync waiting message.
    
    Args:
        sync_file: Path to the sync file being waited for
    
    Returns:
        Formatted sync waiting message
    """
    return f"[Sync] Waiting for benchmark to signal ready: {sync_file}"


def format_sync_ready() -> str:
    """
    Format benchmark ready message.
    
    Returns:
        Formatted sync ready message
    """
    return "[Sync] Benchmark ready, starting campaign"


def format_sync_timeout(timeout: float) -> str:
    """
    Format sync timeout message.
    
    Args:
        timeout: Timeout duration in seconds
    
    Returns:
        Formatted sync timeout message
    """
    return f"[Sync] Timeout waiting for benchmark signal after {timeout}s"


def format_sync_stopped() -> str:
    """
    Format benchmark stopped message.
    
    Returns:
        Formatted sync stopped message
    """
    return "[Sync] Benchmark signal disappeared - stopping campaign gracefully"

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
    Format the campaign startup banner with profile details.
    
    Includes profile arguments based on log level:
    - MINIMAL: No profile args
    - NORMAL: Show args if present
    - VERBOSE: Show args with formatting
    
    Args:
        config: Config object with campaign parameters
    
    Returns:
        Formatted campaign header string
    """
    from fi.core.config.seed_manager import format_seed_source, get_effective_seed
    
    # Format global seed information
    # Show whether it was explicit, generated, or not set
    if config.global_seed is not None:
        global_seed_str = format_seed_source(
            explicit=config.global_seed if not config.global_seed_was_generated else None,
            global_seed=None,  # N/A for global seed itself
            effective=config.global_seed,
            is_generated=config.global_seed_was_generated
        )
    else:
        global_seed_str = "not set"
    
    # Calculate effective seeds using the same logic as profile loaders
    # This uses global seed directly (not derived) when no explicit seed provided
    effective_area_seed = get_effective_seed(
        explicit=config.area_seed,
        global_seed=config.global_seed
    )
    
    effective_time_seed = get_effective_seed(
        explicit=config.time_seed,
        global_seed=config.global_seed
    )
    
    # Format area and time seed sources
    area_seed_str = format_seed_source(
        config.area_seed,
        config.global_seed,
        effective_area_seed,
        is_generated=False  # Only global seed can be generated
    )
    
    time_seed_str = format_seed_source(
        config.time_seed,
        config.global_seed,
        effective_time_seed,
        is_generated=False  # Only global seed can be generated
    )
    
    sep = sty.make_section_separator()
    
    # Build header lines
    header_lines = ["", sep]
    
    # Add debug warning if in debug mode
    if config.debug:
        header_lines.extend([
            "Campaign Configuration [DEBUG MODE]:",
            "",
            "  ⚠️  DEBUG MODE ACTIVE",
            "  ─────────────────────────",
            "  • All code paths execute normally",
            "  • Hardware I/O is simulated with realistic delays",
            "  • Serial responses simulate successful operations",
            "  • No actual injections occur",
            "",
        ])
    else:
        header_lines.append("Campaign Configuration:")
    
    # Add standard configuration info
    header_lines.extend([
        f"  Device: {config.dev} @ {config.baud} baud",
        f"  Area Profile: {config.area_profile}",
    ])
    
    # Add area profile arguments if present
    # Show based on log level (minimal=skip, normal/verbose=show)
    if config.area_args and config.log_level in ("normal", "verbose"):
        if config.log_level == "verbose":
            # Verbose: show formatted args on separate lines
            header_lines.append("    Area Args:")
            for arg_pair in config.area_args.split(","):
                arg_pair = arg_pair.strip()
                if "=" in arg_pair:
                    key, value = arg_pair.split("=", 1)
                    header_lines.append(f"      {key}={value}")
                else:
                    header_lines.append(f"      {arg_pair}")
        else:
            # Normal: show on one line
            header_lines.append(f"    Args: {config.area_args}")
    
    # Add time profile
    header_lines.append(f"  Time Profile: {config.time_profile}")
    
    # Add time profile arguments if present
    if config.time_args and config.log_level in ("normal", "verbose"):
        if config.log_level == "verbose":
            # Verbose: show formatted args on separate lines
            header_lines.append("    Time Args:")
            for arg_pair in config.time_args.split(","):
                arg_pair = arg_pair.strip()
                if "=" in arg_pair:
                    key, value = arg_pair.split("=", 1)
                    header_lines.append(f"      {key}={value}")
                else:
                    header_lines.append(f"      {arg_pair}")
        else:
            # Normal: show on one line
            header_lines.append(f"    Args: {config.time_args}")
    
    # Add seed information
    header_lines.extend([
        f"  Global Seed: {global_seed_str}",
        f"  Area Seed: {area_seed_str}",
        f"  Time Seed: {time_seed_str}",
        sep,
    ])
    
    return "\n".join(header_lines)

def format_campaign_end(stats: Dict[str, Any], termination_reason: str = "unknown") -> str:
    """
    Format the campaign completion banner with termination reason.
    
    Args:
        stats: Dictionary with 'total', 'successes', 'failures' keys
        termination_reason: Why the campaign ended
    
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
        f"  Termination: {termination_reason}\n" +
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


# =============================================================================
# Register Injections Messages
# =============================================================================

def format_reg_inject_init(interface: str, idle_id: int, width: int, max_reg_id: int) -> str:
    """
    Format register injection interface initialization message.
    
    Args:
        interface: Interface type (e.g., "UART")
        idle_id: Idle register ID
        width: Register ID bit width
        max_reg_id: Maximum register ID supported
    
    Returns:
        Formatted initialization message
    """
    return (
        f"[REG_INJECT] Initialized via {interface}: idle_id={idle_id}, "
        f"width={width} bits (supports reg_id 1-{max_reg_id})"
    )


def format_reg_inject_inject(reg_id: int, bit_index: int = None) -> str:
    """
    Format register injection command message.
    
    Args:
        reg_id: Register ID
        bit_index: Optional bit index
    
    Returns:
        Formatted injection message
    """
    if bit_index is None:
        return f"[REG_INJECT] Injecting reg_id={reg_id}"
    else:
        return f"[REG_INJECT] Injecting reg_id={reg_id}, bit={bit_index}"


def format_reg_inject_error(reg_id: int, width: int, max_reg_id: int) -> str:
    """
    Format register injection validation error message.
    
    Args:
        reg_id: Invalid register ID
        width: Register ID bit width
        max_reg_id: Maximum register ID supported
    
    Returns:
        Formatted error message
    """
    return (
        f"[REG_INJECT] ERROR: reg_id={reg_id} out of range "
        f"(1-{max_reg_id} for {width}-bit width)"
    )


def format_reg_inject_placeholder() -> str:
    """
    Format register injection placeholder message for missing transport.
    
    Returns:
        Formatted placeholder message
    """
    return "[REG_INJECT] No transport available - returning success (placeholder)"


# =============================================================================
# SEM Preflight Messages
# =============================================================================

def format_sem_preflight_testing() -> str:
    """
    Format SEM preflight test starting message.
    
    Returns:
        Formatted preflight testing message
    """
    return "[SEM] Testing connection..."


def format_sem_preflight_ok(field_count: int) -> str:
    """
    Format SEM preflight test success message.
    
    Args:
        field_count: Number of status fields received
    
    Returns:
        Formatted preflight OK message
    """
    return f"[SEM] Connection OK - received {field_count} status fields"


def format_sem_preflight_error(error_type: str, required: bool) -> str:
    """
    Format SEM preflight test failure message.
    
    Args:
        error_type: Type of error ("no_response" or exception message)
        required: Whether preflight is required (affects behavior message)
    
    Returns:
        Formatted preflight error message with behavior note
    """
    if error_type == "no_response":
        msg = "[SEM] ERROR: No response from SEM. Check hardware connection."
    else:
        msg = f"[SEM] ERROR: Preflight test failed: {error_type}"
    
    if required:
        msg += "\n[SEM] SEM_PREFLIGHT_REQUIRED=True - aborting campaign."
    else:
        msg += "\n[SEM] Preflight not required - continuing with warning."
    
    return msg


# =============================================================================
# ACME Debug Messages
# =============================================================================

def format_acme_debug(debug_type: str, **kwargs) -> str:
    """
    Format ACME debug message (controlled by FI_ACME_DEBUG env var).
    
    Args:
        debug_type: Type of debug message
        **kwargs: Type-specific parameters
    
    Returns:
        Formatted ACME debug message
    
    Debug types:
        - ebd_stat: path, size
        - payload_stats: rows, words, ones
        - cache_hit: path, lines
        - emit_complete: count, path
        - samples: samples (list)
        - token: lfa
        - word: word_index, la, word, samples
    """
    if debug_type == "ebd_stat":
        size = kwargs.get('size', '<stat failed>')
        return f"[DEBUG][ACME] EBD: {kwargs['path']} — size={size}"
    
    elif debug_type == "payload_stats":
        return (
            f"[DEBUG][ACME] payload_rows={kwargs['rows']}, "
            f"full_32bit_words={kwargs['words']}, ones_bits={kwargs['ones']}"
        )
    
    elif debug_type == "cache_hit":
        return f"[DEBUG][ACME] cache hit: {kwargs['path']} (lines={kwargs['lines']})"
    
    elif debug_type == "emit_complete":
        return f"[DEBUG][ACME] emitted={kwargs['count']} LFAs → {kwargs['path']}"
    
    elif debug_type == "samples":
        samples = kwargs['samples']
        return "[DEBUG][ACME] first LFAs: " + ", ".join(samples)
    
    elif debug_type == "token":
        return f"[DEBUG][ACME] token LFA: {kwargs['lfa']}"
    
    elif debug_type == "word":
        return (
            f"[DEBUG][ACME] W={kwargs['word_index']} → "
            f"(LA={kwargs['la']}, WORD={kwargs['word']}), "
            f"samples={kwargs['samples']}"
        )
    
    # Fallback for unknown debug types
    return f"[DEBUG][ACME] {debug_type}: {kwargs}"


# =============================================================================
# Target List Messages
# =============================================================================

def format_target_list_loading(pool_file: str) -> str:
    """
    Format target list loading message.
    
    Args:
        pool_file: Path to pool file being loaded
    
    Returns:
        Formatted loading message
    """
    return f"[target_list] Loading pool from {pool_file}"


def format_target_list_loaded(count: int) -> str:
    """
    Format target list loaded message.
    
    Args:
        count: Number of targets loaded
    
    Returns:
        Formatted loaded message
    """
    return f"[target_list] Loaded {count} targets from file"


def format_target_list_stats(stats: dict) -> str:
    """
    Format target list statistics message.
    
    Args:
        stats: Pool statistics dictionary with 'by_kind' key
    
    Returns:
        Formatted stats message
    """
    return f"[target_list] Pool breakdown: {stats['by_kind']}"