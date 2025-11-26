# =============================================================================
# FATORI-V • FI Engine Config
# File: engine/config.py
# -----------------------------------------------------------------------------
# Configuration container built from parsed CLI arguments.
#=============================================================================

from dataclasses import dataclass
from typing import Optional

from fi import fi_settings


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
    system_dict_path: Optional[str]
    pool_file_path: Optional[str]

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
    #
    # board_name can be provided explicitly through the CLI, or inferred from
    # the system dictionary. ebd_path points to the EBD file used by ACME.
    board_name: Optional[str]
    default_board_name: str
    ebd_path: Optional[str]

    # GPIO configuration (simplified for serial transmission)
    gpio_enabled: bool = False
    gpio_pin: int = 17
    gpio_idle_id: int = 0
    gpio_reg_id_width: int = 8

    # Seeds for reproducibility
    global_seed: Optional[int] = None
    area_seed: Optional[int] = None
    time_seed: Optional[int] = None


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
    board_name = args.board or None
    pool_file_path = args.pool_file_path or None
    
    # Build Config with complete fallback logic for all settings
    cfg = Config(
        # Serial/SEM configuration
        dev=args.dev,  # Already has default from parser
        baud=int(args.baud),  # Already has default from parser
        sem_clock_hz=get_with_fallback(args, 'sem_clock_hz', fi_settings.SEM_CLOCK_HZ),
        sem_preflight_required=get_with_fallback(args, 'sem_preflight_required', fi_settings.SEM_PREFLIGHT_REQUIRED),
        
        # Profile selection
        area_profile=args.area_profile,  # Already has default from parser
        area_args=area_args,
        time_profile=args.time_profile,  # Already has default from parser
        time_args=time_args,
        
        # File-based inputs
        system_dict_path=args.system_dict_path or fi_settings.SYSTEM_DICT_DEFAULT_PATH,
        pool_file_path=pool_file_path,
        
        # Logging configuration
        log_root_override=log_root_override,
        log_filename=get_with_fallback(args, 'log_filename', fi_settings.LOG_FILENAME),
        log_level=args.log_level,  # Already has default from parser
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
        ebd_path=args.ebd_path or fi_settings.DEFAULT_EBD_PATH,
        
        # GPIO configuration (simplified for serial transmission)
        gpio_enabled=getattr(args, 'gpio_enabled', fi_settings.INJECTION_GPIO_ENABLED),
        gpio_pin=get_with_fallback(args, 'gpio_pin', fi_settings.INJECTION_GPIO_PIN),
        gpio_idle_id=get_with_fallback(args, 'gpio_idle_id', fi_settings.INJECTION_GPIO_IDLE_ID),
        gpio_reg_id_width=get_with_fallback(args, 'gpio_reg_id_width', fi_settings.INJECTION_GPIO_REG_ID_WIDTH),
        
        # Seeds for reproducibility
        global_seed=getattr(args, 'global_seed', None),
        area_seed=getattr(args, 'area_seed', None),
        time_seed=getattr(args, 'time_seed', None),
    )

    return cfg