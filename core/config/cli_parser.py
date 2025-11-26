# =============================================================================
# FATORI-V • FI CLI Parsing
# File: cli/parser.py
# -----------------------------------------------------------------------------
# Argument parser for the FI console command line interface.
#=============================================================================

import argparse

from fi import fi_settings


def _add_serial_args(parser: argparse.ArgumentParser) -> None:
    """
    Add SEM serial-port related arguments to the parser.

    These control how the FI console talks to the SEM controller over UART.
    """
    parser.add_argument(
        "-d",
        "--dev",
        dest="dev",
        default=fi_settings.DEFAULT_SEM_DEVICE,
        help=(
            "Serial device used to talk to SEM "
            f"(default: {fi_settings.DEFAULT_SEM_DEVICE})"
        ),
    )

    parser.add_argument(
        "-b",
        "--baud",
        dest="baud",
        type=int,
        default=fi_settings.DEFAULT_SEM_BAUDRATE,
        help=(
            "Baudrate for the SEM serial link "
            f"(default: {fi_settings.DEFAULT_SEM_BAUDRATE})"
        ),
    )

    # SEM preflight requirement (paired flags for boolean control)
    parser.add_argument(
        "--sem-preflight-required",
        dest="sem_preflight_required",
        action="store_true",
        default=None,
        help=(
            "Require SEM preflight test to pass - abort campaign on failure "
            f"(default: {fi_settings.SEM_PREFLIGHT_REQUIRED})"
        )
    )
    parser.add_argument(
        "--no-sem-preflight-required",
        dest="sem_preflight_required",
        action="store_false",
        help="Allow campaign to continue even if SEM preflight test fails (warn only)"
    )


def _add_profile_args(parser: argparse.ArgumentParser) -> None:
    """
    Add area/time profile selection arguments to the parser.

    Area profiles are responsible for building a TargetPool, and time profiles
    decide when injections should happen.
    """
    parser.add_argument(
        "--area",
        dest="area_profile",
        default=fi_settings.DEFAULT_AREA_PROFILE,
        help=(
            "Area profile to use for building the target pool "
            f"(default: {fi_settings.DEFAULT_AREA_PROFILE!r})"
        ),
    )

    parser.add_argument(
        "--area-args",
        dest="area_args",
        default=fi_settings.DEFAULT_AREA_ARGS,
        help=(
            "Opaque argument string passed to the area profile "
            f"(default: {fi_settings.DEFAULT_AREA_ARGS!r})"
        ),
    )

    parser.add_argument(
        "--time",
        dest="time_profile",
        default=fi_settings.DEFAULT_TIME_PROFILE,
        help=(
            "Time profile to use for scheduling injections "
            f"(default: {fi_settings.DEFAULT_TIME_PROFILE!r})"
        ),
    )

    parser.add_argument(
        "--time-args",
        dest="time_args",
        default=fi_settings.DEFAULT_TIME_ARGS,
        help=(
            "Opaque argument string passed to the time profile "
            f"(default: {fi_settings.DEFAULT_TIME_ARGS!r})"
        ),
    )


def _add_file_args(parser: argparse.ArgumentParser) -> None:
    """
    Add file paths for system dictionary and injection pool.

    These allow the user to override the default paths for configuration files.
    """
    parser.add_argument(
        "--system-dict",
        dest="system_dict_path",
        default=fi_settings.SYSTEM_DICT_DEFAULT_PATH,
        help=(
            "Path to the system dictionary YAML file describing the board, "
            "modules, registers and pblocks "
            f"(default: {fi_settings.SYSTEM_DICT_DEFAULT_PATH!r})"
        ),
    )

    parser.add_argument(
        "--pool-file",
        dest="pool_file_path",
        default=fi_settings.INJECTION_POOL_DEFAULT_PATH,
        help=(
            "Optional path to an injection pool file. When provided, this is "
            "used to pre-seed the TargetPool. "
            f"(default: {fi_settings.INJECTION_POOL_DEFAULT_PATH!r})"
        ),
    )


def _add_board_args(parser: argparse.ArgumentParser) -> None:
    """
    Add board and EBD configuration arguments.

    These determine which FPGA board we are targeting and where to find
    the essential bit database file for ACME.
    """
    parser.add_argument(
        "--board",
        dest="board",
        default=None,
        help=(
            "Logical board name for ACME and system dictionary resolution "
            "(for example 'basys3' or 'xcku040'). If not provided, FI will "
            "attempt to use the board specified in the system dictionary, or "
            "fall back to a built-in default."
        ),
    )

    parser.add_argument(
        "--ebd-path",
        dest="ebd_path",
        default=fi_settings.DEFAULT_EBD_PATH,
        help=(
            "Path to the EBD file used by ACME to map regions to "
            f"configuration bits (default: {fi_settings.DEFAULT_EBD_PATH!r})"
        ),
    )


def _add_logging_args(parser: argparse.ArgumentParser) -> None:
    """
    Add logging and output-directory arguments.

    Controls where logs are written and how verbose the output should be.
    """
    parser.add_argument(
        "--log-root",
        dest="log_root",
        default=fi_settings.LOG_ROOT,
        help=(
            "Base directory for FI logs "
            f"(default: {fi_settings.LOG_ROOT!r})"
        ),
    )
    
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["minimal", "normal", "verbose"],
        default=fi_settings.LOG_LEVEL,
        help=(
            "Console output verbosity level. "
            "minimal: only errors and summary. "
            "normal: major steps and progress. "
            "verbose: everything including individual injections. "
            f"(default: {fi_settings.LOG_LEVEL!r}). "
            "See fi/config/log_levels.py to customize level definitions."
        ),
    )

def _add_gpio_args(parser: argparse.ArgumentParser) -> None:
    """
    Add GPIO configuration arguments for register injection.
    
    The FI system uses a single GPIO pin for serial transmission of
    register IDs to the FPGA. When idle, it transmits IDLE_ID (default 0).
    When injecting, it transmits the target register ID.
    """
    gpio_group = parser.add_argument_group(
        "GPIO Configuration",
        "Options for register injection via GPIO serial transmission"
    )
    
    gpio_group.add_argument(
        "--gpio-enabled",
        action="store_true",
        help="Enable GPIO control for register injection (default: NoOp simulation mode)"
    )
    
    gpio_group.add_argument(
        "--gpio-pin",
        type=int,
        default=None,
        help=f"GPIO pin number for register ID transmission (default: {fi_settings.INJECTION_GPIO_PIN})"
    )
    
    gpio_group.add_argument(
        "--gpio-idle-id",
        type=int,
        default=None,
        help=f"Idle value when no injection active (default: {fi_settings.INJECTION_GPIO_IDLE_ID})"
    )
    
    gpio_group.add_argument(
        "--gpio-reg-id-width",
        type=int,
        default=None,
        help=f"Bit width for register IDs (default: {fi_settings.INJECTION_GPIO_REG_ID_WIDTH})"
    )

def _add_seed_args(parser: argparse.ArgumentParser) -> None:
    """
    Add seed arguments for reproducible campaigns.

    Seed control allows fully reproducible fault injection campaigns by
    controlling randomization in both area and time profiles.
    """
    seed_group = parser.add_argument_group(
        "Seeds (Reproducibility)",
        "Control random behavior for reproducible campaigns"
    )

    seed_group.add_argument(
        "--global-seed",
        type=int,
        default=None,
        help=(
            "Master seed for campaign. Area and time seeds will be derived "
            "from this unless explicitly overridden."
        ),
    )

    seed_group.add_argument(
        "--area-seed",
        type=int,
        default=None,
        help=(
            "Explicit seed for area profile. Overrides global-seed derivation. "
            "Controls target selection order."
        ),
    )

    seed_group.add_argument(
        "--time-seed",
        type=int,
        default=None,
        help=(
            "Explicit seed for time profile. Overrides global-seed derivation. "
            "Controls injection timing randomness."
        ),
    )


def _add_all_settings_overrides(parser: argparse.ArgumentParser) -> None:
    """
    Add CLI arguments for all remaining fi_settings.py values.
    
    This allows users to override any setting without modifying fi_settings.py.
    Provides complete control over all FI behavior via command line.
    """
    
    # General settings group
    general_group = parser.add_argument_group(
        "General Settings",
        "Override general FI console settings"
    )
    
    general_group.add_argument(
        "--default-board",
        type=str,
        default=None,
        help=(
            "Default board name when not explicitly specified "
            f"(default: {fi_settings.DEFAULT_BOARD_NAME!r})"
        )
    )
    
    general_group.add_argument(
        "--sem-clock-hz",
        type=int,
        default=None,
        help=(
            "SEM IP core clock frequency in Hz "
            f"(default: {fi_settings.SEM_CLOCK_HZ})"
        )
    )
    
    general_group.add_argument(
        "--log-filename",
        type=str,
        default=None,
        help=(
            "Injection log filename "
            f"(default: {fi_settings.LOG_FILENAME!r})"
        )
    )
    
    # Logging toggles group
    # These use paired flags (--flag / --no-flag) for boolean control
    log_toggles = parser.add_argument_group(
        "Logging Toggles",
        "Enable/disable specific logging categories. "
        "Use --flag to enable, --no-flag to disable."
    )
    
    # SystemDict loading
    log_toggles.add_argument(
        "--log-systemdict",
        dest="log_systemdict",
        action="store_true",
        default=None,
        help="Enable SystemDict loading logs"
    )
    log_toggles.add_argument(
        "--no-log-systemdict",
        dest="log_systemdict",
        action="store_false",
        help="Disable SystemDict loading logs"
    )
    
    # Board resolution
    log_toggles.add_argument(
        "--log-board-resolution",
        dest="log_board_resolution",
        action="store_true",
        default=None,
        help="Enable board resolution logs"
    )
    log_toggles.add_argument(
        "--no-log-board-resolution",
        dest="log_board_resolution",
        action="store_false",
        help="Disable board resolution logs"
    )
    
    # ACME expansion
    log_toggles.add_argument(
        "--log-acme",
        dest="log_acme",
        action="store_true",
        default=None,
        help="Enable ACME expansion logs"
    )
    log_toggles.add_argument(
        "--no-log-acme",
        dest="log_acme",
        action="store_false",
        help="Disable ACME expansion logs"
    )
    
    # Pool building
    log_toggles.add_argument(
        "--log-pool-building",
        dest="log_pool_building",
        action="store_true",
        default=None,
        help="Enable pool building logs"
    )
    log_toggles.add_argument(
        "--no-log-pool-building",
        dest="log_pool_building",
        action="store_false",
        help="Disable pool building logs"
    )
    
    # Individual injections
    log_toggles.add_argument(
        "--log-injections",
        dest="log_injections",
        action="store_true",
        default=None,
        help="Enable individual injection logs"
    )
    log_toggles.add_argument(
        "--no-log-injections",
        dest="log_injections",
        action="store_false",
        help="Disable individual injection logs"
    )
    
    # SEM commands
    log_toggles.add_argument(
        "--log-sem-commands",
        dest="log_sem_commands",
        action="store_true",
        default=None,
        help="Enable SEM command logs"
    )
    log_toggles.add_argument(
        "--no-log-sem-commands",
        dest="log_sem_commands",
        action="store_false",
        help="Disable SEM command logs"
    )
    
    # Errors
    log_toggles.add_argument(
        "--log-errors",
        dest="log_errors",
        action="store_true",
        default=None,
        help="Enable error logs"
    )
    log_toggles.add_argument(
        "--no-log-errors",
        dest="log_errors",
        action="store_false",
        help="Disable error logs"
    )
    
    # Campaign start/end
    log_toggles.add_argument(
        "--log-campaign",
        dest="log_campaign",
        action="store_true",
        default=None,
        help="Enable campaign start/end logs"
    )
    log_toggles.add_argument(
        "--no-log-campaign",
        dest="log_campaign",
        action="store_false",
        help="Disable campaign start/end logs"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build the complete argument parser for the FI console.

    Returns:
        Configured ArgumentParser ready to parse sys.argv
    """
    parser = argparse.ArgumentParser(
        prog="fi",
        description="FATORI-V Fault Injection console",
    )

    _add_serial_args(parser)
    _add_profile_args(parser)
    _add_file_args(parser)
    _add_board_args(parser)
    _add_logging_args(parser)
    _add_gpio_args(parser)
    _add_seed_args(parser)
    _add_all_settings_overrides(parser)

    return parser


def parse_args(argv=None) -> argparse.Namespace:
    """
    Parse command-line arguments for the FI console.

    Args:
        argv: Optional list of arguments (for testing). If None, uses sys.argv.

    Returns:
        Parsed arguments as argparse.Namespace
    """
    parser = build_arg_parser()
    return parser.parse_args(argv)