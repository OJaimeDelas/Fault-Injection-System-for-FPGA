# =============================================================================
# FATORI-V • FI CLI Parsing
# File: core/config/cli_parser.py
# -----------------------------------------------------------------------------
# Argument parser for the FI console command line interface.
#=============================================================================

import argparse

from fi import fi_settings


def _add_debug_args(parser: argparse.ArgumentParser) -> None:
    """
    Add debug mode arguments.
    
    Debug mode simulates hardware without actual connections,
    useful for testing campaign logic without the board.
    """
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help=(
            "Debug mode: simulate hardware without board connection. "
            "All injection logic runs normally but hardware I/O is stubbed. "
            "Useful for testing pool building, ratio enforcement, and campaign flow."
        ),
    )

def _add_serial_args(parser: argparse.ArgumentParser) -> None:
    """
    Add SEM serial-port related arguments to the parser.

    These control how the FI console talks to the SEM controller over UART.
    """
    parser.add_argument(
        "-d",
        "--dev",
        dest="dev",
        default=fi_settings.DEFAULT_DEVICE,
        help=(
            "Serial device used to talk to SEM "
            f"(default: {fi_settings.DEFAULT_DEVICE})"
        ),
    )

    parser.add_argument(
        "-b",
        "--baud",
        dest="baud",
        type=int,
        default=fi_settings.DEFAULT_BAUDRATE,
        help=(
            "Baudrate for the SEM serial link "
            f"(default: {fi_settings.DEFAULT_BAUDRATE})"
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
    Add file-path related arguments to the parser.

    These control where key input files (system dictionary, EBD) are located.
    """
    parser.add_argument(
        "--system-dict",
        dest="system_dict_path",
        default=fi_settings.SYSTEM_DICT_DEFAULT_PATH,
        help=(
            "Path to system dictionary YAML "
            f"(default: {fi_settings.SYSTEM_DICT_DEFAULT_PATH!r})"
        ),
    )

    parser.add_argument(
        "--ebd",
        dest="ebd_path",
        default=fi_settings.DEFAULT_EBD_PATH,
        help=(
            "Path to Essential Bits Data file (.ebd) "
            f"(default: {fi_settings.DEFAULT_EBD_PATH!r})"
        ),
    )


def _add_board_args(parser: argparse.ArgumentParser) -> None:
    """
    Add board-selection arguments to the parser.

    Board selection can be explicit (--board) or auto-detected.
    """
    parser.add_argument(
        "--board",
        dest="board_name",
        default=None,
        help=(
            "Board/device name to use (e.g., 'basys3', 'xcku040'). "
            "If not provided, will be auto-detected from environment or settings."
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
            "Console output verbosity level: minimal (errors only), "
            "normal (campaign summary), verbose (all details) "
            f"(default: {fi_settings.LOG_LEVEL!r})"
        ),
    )


def _add_reg_inject_args(parser: argparse.ArgumentParser) -> None:
    """
    Add register injection arguments.
    
    Configuration for UART-based register fault injection via fi_coms protocol.
    """
    reg_group = parser.add_argument_group(
        'Register Injection Configuration',
        'UART-based register injection via fi_coms hardware module'
    )
    
    reg_group.add_argument(
        '--reg-inject-disabled',
        action='store_true',
        dest='reg_inject_disabled',
        help=(
            "Disable register injection even if REG targets exist "
            "(REG injections will be simulated with NoOp). "
            f"Default: {fi_settings.INJECTION_REG_FORCE_DISABLED}"
        )
    )
    
    reg_group.add_argument(
        '--reg-inject-idle-id',
        type=int,
        metavar='ID',
        help=f"Idle register ID value (0). Default: {fi_settings.INJECTION_REG_IDLE_ID}"
    )
    
    reg_group.add_argument(
        '--reg-inject-reg-id-width',
        type=int,
        metavar='BITS',
        help=f"Register ID bit width (8 = IDs 1-255). Default: {fi_settings.INJECTION_REG_ID_WIDTH}"
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

def _add_tpool_export_args(parser: argparse.ArgumentParser) -> None:
    """
    Add TargetPool YAML export arguments.
    
    Controls automatic export of generated target pools to YAML files for
    reproducibility and debugging. Exported pools can be reused with the
    target_list area profile.
    """
    tpool_group = parser.add_argument_group(
        "TargetPool Export",
        "Control automatic YAML export of generated target pools"
    )
    
    tpool_group.add_argument(
        "--tpool-name",
        type=str,
        default=None,
        help=(
            "Custom name for pool YAML file (without extension). "
            "If not provided, uses timestamp-based name. "
            "Example: --tpool-name campaign_baseline"
        ),
    )
    
    tpool_group.add_argument(
        "--tpool-output",
        type=str,
        default=None,
        help=(
            "Additional directory to copy pool YAML to. "
            "Pool is always saved to primary location (fi/gen/tpool/), "
            "this provides a convenient copy to a user-specified path. "
            "Example: --tpool-output /tmp/my_pools"
        ),
    )
    
    tpool_group.add_argument(
        "--tpool-output-dir",
        type=str,
        default=None,
        help=(
            "Override primary output directory for pool YAML files. "
            f"(default: {fi_settings.TPOOL_OUTPUT_DIR})"
        ),
    )
    
    tpool_group.add_argument(
        "--no-tpool-save",
        action="store_true",
        help=(
            "Disable automatic pool YAML generation. "
            "Pool will only exist in memory during campaign execution."
        ),
    )
    
    tpool_group.add_argument(
        "--tpool-size-break-repeat-only",
        type=lambda x: x.lower() in ('true', '1', 'yes', 'on'),
        default=None,
        metavar='BOOL',
        help=(
            "Control when tpool_size limit applies. "
            "true: tpool_size only applies when repeat=true (default). "
            "false: tpool_size always applies. "
            "Example: --tpool-size-break-repeat-only false"
        ),
    )
    
    tpool_group.add_argument(
        "--tpool-absolute-cap",
        type=int,
        default=None,
        help=(
            "Absolute safety cap on pool size. Prevents creation of "
            "extremely large pools. "
            f"(default: {fi_settings.TPOOL_ABSOLUTE_CAP})"
        ),
    )

    tpool_group.add_argument(
        "--ratio-strict",
        action="store_true",
        default=False,
        help=(
            "Enforce strict ratio - stop pool when minority kind exhausts. "
            "Example: ratio=1.0 with 186 REGs stops at 186 targets instead of "
            "falling back to CONFIG. Without this flag, pool continues with "
            "majority kind after minority exhausts."
        ),
    )

def _add_acme_args(parser: argparse.ArgumentParser) -> None:
    """
    Add ACME caching arguments.
    
    ACME is used to expand pblock regions to configuration bit addresses.
    Caching significantly speeds up repeated campaigns with the same modules.
    """
    acme_group = parser.add_argument_group(
        "ACME Caching",
        "Control caching of ACME configuration bit expansions"
    )
    
    acme_group.add_argument(
        "--no-acme-cache",
        action="store_true",
        default=False,
        help=(
            "Disable ACME result caching. "
            "ACME will be called fresh for every module expansion. "
            "Useful for testing or when pblock definitions change frequently."
        ),
    )
    
    acme_group.add_argument(
        "--acme-cache-dir",
        type=str,
        default=None,
        help=(
            "Directory for ACME cache files (relative to project root). "
            f"Default: {fi_settings.ACME_CACHE_DIR}"
        ),
    )


def _add_benchmark_sync_args(parser: argparse.ArgumentParser) -> None:
    """
    Add benchmark synchronization arguments.
    
    Controls file-based synchronization with external benchmark processes.
    The FI system waits for a signal file to appear before starting, and
    stops gracefully if the file is removed during execution.
    """
    sync_group = parser.add_argument_group(
        "Benchmark Synchronization",
        "Synchronize FI with external benchmark via signal file"
    )
    
    sync_group.add_argument(
        "--wait-for-file",
        type=str,
        default=None,
        help=(
            "Wait for this file to appear before starting campaign. "
            "Campaign stops if file is removed during execution. " 
            "Dir path starts at fi/."
            "Example: --wait-for-file /tmp/benchmark_ready"
        ),
    )
    
    sync_group.add_argument(
        "--check-interval",
        type=float,
        default=None,
        help=(
            "Check signal file existence every N seconds. "
            "Works in combination with --check-every-n (whichever comes first). "
            f"(default: {fi_settings.BENCHMARK_CHECK_INTERVAL_S})"
        ),
    )
    
    sync_group.add_argument(
        "--check-every-n",
        type=int,
        default=None,
        help=(
            "Check signal file existence every N injections. "
            "Works in combination with --check-interval (whichever comes first). "
            f"(default: {fi_settings.BENCHMARK_CHECK_EVERY_N_INJECTIONS})"
        ),
    )
    
    sync_group.add_argument(
        "--sync-timeout",
        type=float,
        default=None,
        help=(
            "Maximum seconds to wait for signal file to appear. "
            "Campaign aborts if timeout is reached. "
            "None = wait forever. "
            f"(default: {fi_settings.BENCHMARK_SYNC_TIMEOUT})"
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
            "Set default board name "
            f"(current: {fi_settings.DEFAULT_BOARD_NAME})"
        )
    )
    
    general_group.add_argument(
        "--log-file-basename",
        type=str,
        default=None,
        help=(
            "Override log file basename "
            f"(current: {fi_settings.LOG_FILENAME})"
        )
    )
    
    # Message toggles group
    log_toggles = parser.add_argument_group(
        "Message Toggles",
        "Fine-grained control over what gets logged"
    )
    
    # System dictionary loading
    log_toggles.add_argument(
        "--log-systemdict",
        dest="log_systemdict",
        action="store_true",
        default=None,
        help="Enable system dictionary loading logs"
    )
    log_toggles.add_argument(
        "--no-log-systemdict",
        dest="log_systemdict",
        action="store_false",
        help="Disable system dictionary loading logs"
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
    
    # Pool building
    log_toggles.add_argument(
        "--log-pool-built",
        dest="log_pool_built",
        action="store_true",
        default=None,
        help="Enable pool building logs"
    )
    log_toggles.add_argument(
        "--no-log-pool-built",
        dest="log_pool_built",
        action="store_false",
        help="Disable pool building logs"
    )
    
    # ACME expansion
    log_toggles.add_argument(
        "--log-acme-expansion",
        dest="log_acme_expansion",
        action="store_true",
        default=None,
        help="Enable ACME region expansion logs"
    )
    log_toggles.add_argument(
        "--no-log-acme-expansion",
        dest="log_acme_expansion",
        action="store_false",
        help="Disable ACME region expansion logs"
    )
    
    # SEM preflight
    log_toggles.add_argument(
        "--log-sem-preflight",
        dest="log_sem_preflight",
        action="store_true",
        default=None,
        help="Enable SEM preflight logs"
    )
    log_toggles.add_argument(
        "--no-log-sem-preflight",
        dest="log_sem_preflight",
        action="store_false",
        help="Disable SEM preflight logs"
    )
    
    # Injections
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
    _add_debug_args(parser)
    _add_reg_inject_args(parser)
    _add_seed_args(parser)
    _add_tpool_export_args(parser)  
    _add_benchmark_sync_args(parser)  
    _add_all_settings_overrides(parser)
    _add_acme_args(parser)

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