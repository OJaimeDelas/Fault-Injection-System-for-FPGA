# =============================================================================
# FATORI-V • FI Engine Config
# File: core/config/config.py
# -----------------------------------------------------------------------------
# Configuration container built from parsed CLI arguments.
#=============================================================================

from dataclasses import dataclass
from typing import Optional

from fi import fi_settings
from fi.core.config.seed_manager import generate_global_seed


@dataclass
class Config:
    """
    Simple container for FI runtime configuration.

    This object is intentionally kept as a dumb data holder: it does not contain
    any complex logic. All decisions (such as how to interpret board names or
    where to store logs) are made by the engine modules that consume it.
    
    Every setting from fi_settings.py is represented here, allowing complete
    CLI override without editing fi_settings.py.
    """

    # Serial / SEM configuration
    dev: str
    baud: int
    sem_clock_hz: int
    sem_preflight_required: bool

    # Area/time profile selection and their opaque argument strings
    area_profile: str
    area_args: Optional[str]
    time_profile: str
    time_args: Optional[str]

    # File-based inputs
    system_dict_path: str
    system_dict_is_user_path: bool  # Track if user provided this path
    ebd_path: str
    ebd_is_user_path: bool  # Track if user provided this path
    pool_file_path: Optional[str]
    pool_file_is_user_path: bool  # Track if user provided this path

    # Logging configuration
    log_root_override: Optional[str]
    log_filename: str
    log_level: str  # "minimal", "normal", or "verbose" (see log_levels.py)
    log_systemdict: bool
    log_board_resolution: bool
    log_acme: bool
    log_pool_building: bool
    log_injections: bool
    log_sem_commands: bool
    log_errors: bool
    log_campaign: bool

    # Board and ACME/EBD configuration
    board_name: Optional[str]
    default_board_name: str

    # GPIO configuration (auto-enabled based on pool analysis)
    gpio_force_disabled: bool = False
    gpio_pin: int = 17
    gpio_idle_id: int = 0
    gpio_reg_id_width: int = 8

    # Seeds for reproducibility
    global_seed: Optional[int] = None
    global_seed_was_generated: bool = False  # Track if global_seed was auto-generated
    area_seed: Optional[int] = None
    time_seed: Optional[int] = None

    # TargetPool export configuration (Phase 8)
    tpool_auto_save: bool = True
    tpool_output_dir: str = "fi/gen/tpool"
    tpool_output_name: Optional[str] = None
    tpool_additional_path: Optional[str] = None

    # TargetPool size control
    tpool_size_break_repeat_only: bool = True
    tpool_absolute_cap: int = 1_000_000
    ratio_strict: bool = False

    acme_cache_enabled: bool = True
    acme_cache_dir: str = "gen/acme"

    # Benchmark synchronization configuration (Phase 9)
    benchmark_sync_enabled: bool = False
    benchmark_sync_file: Optional[str] = None
    benchmark_check_interval_s: float = 1.0
    benchmark_check_every_n: int = 100
    benchmark_sync_timeout: Optional[float] = None

    # Debug mode (testing without hardware)
    debug: bool = False 

    # ACME caching configuration
    acme_cache_enabled: bool = True

def build_config(args) -> Config:
    """
    Build a Config instance from the parsed CLI arguments.
    
    Implements fallback chain: CLI argument → fi_settings → error (if required)
    
    For every setting:
    1. Check if CLI argument provided (not None)
    2. If yes, use CLI value
    3. If no, use fi_settings.py value
    
    This allows users to override any setting via CLI without editing fi_settings.py.
    """
    
    def get_with_fallback(args, arg_name: str, settings_value):
        """
        Get value from CLI args with fallback to fi_settings.
        
        Args:
            args: Parsed CLI arguments namespace
            arg_name: Attribute name in args
            settings_value: Fallback value from fi_settings
            
        Returns:
            CLI value if provided (not None), otherwise settings_value
        """
        cli_value = getattr(args, arg_name, None)
        return cli_value if cli_value is not None else settings_value
    
    # Normalize empty strings to None for optional paths and argument strings
    area_args = args.area_args or None
    time_args = args.time_args or None
    log_root_override = args.log_root or None
    board_name = args.board_name or None
    pool_file_path = getattr(args, 'pool_file_path', None)
    
    # Track which paths are user-provided vs defaults
    system_dict_from_cli = hasattr(args, 'system_dict_path') and args.system_dict_path != fi_settings.SYSTEM_DICT_DEFAULT_PATH
    system_dict_path = args.system_dict_path if system_dict_from_cli else fi_settings.SYSTEM_DICT_DEFAULT_PATH
    
    ebd_from_cli = hasattr(args, 'ebd_path') and args.ebd_path != fi_settings.DEFAULT_EBD_PATH
    ebd_path = args.ebd_path if ebd_from_cli else fi_settings.DEFAULT_EBD_PATH
    
    pool_file_from_cli = pool_file_path is not None
    
    # TargetPool export configuration (Phase 8)
    tpool_auto_save = not getattr(args, 'no_tpool_save', False)
    tpool_output_dir = get_with_fallback(args, 'tpool_output_dir', fi_settings.TPOOL_OUTPUT_DIR)
    tpool_output_name = getattr(args, 'tpool_name', None)
    tpool_additional_path = getattr(args, 'tpool_output', None)
    ratio_strict=get_with_fallback(args, 'ratio_strict', fi_settings.RATIO_STRICT_MODE)

    # Handle tpool size control settings
    tpool_size_break_repeat_only = args.tpool_size_break_repeat_only if args.tpool_size_break_repeat_only is not None else fi_settings.TPOOL_SIZE_BREAK_REPEAT_ONLY
    tpool_absolute_cap = args.tpool_absolute_cap if args.tpool_absolute_cap is not None else fi_settings.TPOOL_ABSOLUTE_CAP
    
    # Benchmark synchronization configuration 
    benchmark_sync_file_raw = getattr(args, 'wait_for_file', None)

    # All sync file paths are relative to project root (directory containing fi/)
    if benchmark_sync_file_raw:
        from pathlib import Path
        # Strip leading slash if present, then resolve relative to cwd (project root)
        path_str = benchmark_sync_file_raw.lstrip('/')
        benchmark_sync_file = str(Path.cwd() / path_str)
    else:
        benchmark_sync_file = None

    benchmark_sync_enabled = benchmark_sync_file is not None

    benchmark_check_interval_s = get_with_fallback(
        args, 'check_interval', fi_settings.BENCHMARK_CHECK_INTERVAL_S
    )
    benchmark_check_every_n = get_with_fallback(
        args, 'check_every_n', fi_settings.BENCHMARK_CHECK_EVERY_N_INJECTIONS
    )
    benchmark_sync_timeout = getattr(args, 'sync_timeout', None)
    
    # Seed management: generate global seed if none provided
    # This ensures campaigns are always reproducible by default
    cli_global_seed = getattr(args, 'global_seed', None)
    cli_area_seed = getattr(args, 'area_seed', None)
    cli_time_seed = getattr(args, 'time_seed', None)
    
    # Generate global seed if no seeds provided at all
    if cli_global_seed is None and cli_area_seed is None and cli_time_seed is None:
        # No seeds specified - generate a global seed for reproducibility
        global_seed = generate_global_seed()
        global_seed_was_generated = True
    elif cli_global_seed is None and (cli_area_seed is not None or cli_time_seed is not None):
        # Specific seed(s) provided but no global - generate global for other profiles
        global_seed = generate_global_seed()
        global_seed_was_generated = True
    else:
        # Global seed explicitly provided via CLI
        global_seed = cli_global_seed
        global_seed_was_generated = False

    # Build Config with complete fallback logic for all settings
    cfg = Config(
        # Serial/SEM configuration
        dev=args.dev,
        baud=int(args.baud),
        sem_clock_hz=get_with_fallback(args, 'sem_clock_hz', fi_settings.SEM_CLOCK_HZ),
        sem_preflight_required=get_with_fallback(args, 'sem_preflight_required', fi_settings.SEM_PREFLIGHT_REQUIRED),
        
        # Profile selection
        area_profile=args.area_profile,
        area_args=area_args,
        time_profile=args.time_profile,
        time_args=time_args,
        
        # File-based inputs with tracking
        system_dict_path=system_dict_path,
        system_dict_is_user_path=system_dict_from_cli,
        ebd_path=ebd_path,
        ebd_is_user_path=ebd_from_cli,
        pool_file_path=pool_file_path,
        pool_file_is_user_path=pool_file_from_cli,
        
        # Logging configuration
        log_root_override=log_root_override,
        log_filename=get_with_fallback(args, 'log_filename', fi_settings.LOG_FILENAME),
        log_level=args.log_level,
        log_systemdict=get_with_fallback(args, 'log_systemdict', True),
        log_board_resolution=get_with_fallback(args, 'log_board_resolution', True),
        log_acme=get_with_fallback(args, 'log_acme', True),
        log_pool_building=get_with_fallback(args, 'log_pool_building', True),
        log_injections=get_with_fallback(args, 'log_injections', True),
        log_sem_commands=get_with_fallback(args, 'log_sem_commands', True),
        log_errors=get_with_fallback(args, 'log_errors', True),
        log_campaign=get_with_fallback(args, 'log_campaign', True),
        
        # Board configuration
        board_name=board_name,
        default_board_name=get_with_fallback(args, 'default_board', fi_settings.DEFAULT_BOARD_NAME),
        
        # GPIO configuration
        gpio_force_disabled=getattr(args, 'gpio_disabled', fi_settings.INJECTION_GPIO_FORCE_DISABLED),
        gpio_pin=get_with_fallback(args, 'gpio_pin', fi_settings.INJECTION_GPIO_PIN),
        gpio_idle_id=get_with_fallback(args, 'gpio_idle_id', fi_settings.INJECTION_GPIO_IDLE_ID),
        gpio_reg_id_width=get_with_fallback(args, 'gpio_reg_id_width', fi_settings.INJECTION_GPIO_REG_ID_WIDTH),
        
        # Seeds for reproducibility
        global_seed=global_seed,
        global_seed_was_generated=global_seed_was_generated,
        area_seed=cli_area_seed,
        time_seed=cli_time_seed,
        
        # TargetPool export configuration
        tpool_auto_save=tpool_auto_save,
        tpool_output_dir=args.tpool_output_dir or fi_settings.TPOOL_OUTPUT_DIR,
        tpool_output_name=args.tpool_name or fi_settings.TPOOL_OUTPUT_NAME,
        tpool_additional_path=args.tpool_output or fi_settings.TPOOL_ADDITIONAL_PATH,
        tpool_size_break_repeat_only=tpool_size_break_repeat_only,
        tpool_absolute_cap=tpool_absolute_cap,
        ratio_strict=ratio_strict,
        
        # Benchmark synchronization configuration
        benchmark_sync_enabled=benchmark_sync_enabled,
        benchmark_sync_file=benchmark_sync_file,
        benchmark_check_interval_s=benchmark_check_interval_s,
        benchmark_check_every_n=benchmark_check_every_n,
        benchmark_sync_timeout=benchmark_sync_timeout,

        debug=getattr(args, 'debug', False),
        
        # ACME caching
        acme_cache_enabled=not getattr(args, 'no_acme_cache', False),
        acme_cache_dir=get_with_fallback(args, 'acme_cache_dir', fi_settings.ACME_CACHE_DIR),
    )

    return cfg