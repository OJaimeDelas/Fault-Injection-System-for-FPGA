# =============================================================================
# FATORI-V • FI Settings Control Panel
# File: fi_settings.py
# -----------------------------------------------------------------------------
# Centralised runtime defaults and user-tunable knobs for the FI console.
#=============================================================================


# -----------------------------------------------------------------------------
# General Settings
# -----------------------------------------------------------------------------

# Default board
DEFAULT_BOARD_NAME = "xcku040"

# Ratio behavior control
# When True: Stop pool building when minority kind exhausts (strict ratio enforcement)
# When False: Fall back to majority kind after minority exhausts (maximize pool size)
RATIO_STRICT_MODE = False

# Default serial device used to talk to the SEM controller.
DEFAULT_DEVICE = "/dev/ttyUSB0"

# Default baudrate of the serial link to SEM.
DEFAULT_BAUDRATE = 1250000

# -----------------------------------------------------------------------------
# Serial / SEM control
# -----------------------------------------------------------------------------


# Clock frequency of the SEM IP core on the FPGA, in hertz.
# This is provided so that timing-related calculations can be made when needed.
SEM_CLOCK_HZ = 100_000_000

# Require successful SEM preflight test before starting campaign
SEM_PREFLIGHT_REQUIRED = False


# -----------------------------------------------------------------------------
# System Dictionary
# -----------------------------------------------------------------------------

# Default path to the system dictionary YAML file. This file contains the
# hardware description including boards, modules, registers, and pblocks.
SYSTEM_DICT_DEFAULT_PATH = "core/config/system_dict.yaml"


# -----------------------------------------------------------------------------
# Injection Pool
# -----------------------------------------------------------------------------

# Default path to injection pool file (if using explicit pool)
INJECTION_POOL_DEFAULT_PATH = "profiles/area/examples/sample_pool.yaml"


# -----------------------------------------------------------------------------
# Logging configuration
# -----------------------------------------------------------------------------

# Root directory where FI logs should be stored when the user does not override
# the log root via CLI.
LOG_ROOT = "."

# Base filename for the main FI event log. The full path is computed by the
# logging setup module; callers must not append extensions or directories.
LOG_FILENAME = "injection_log.txt"

# Verbosity level: Controls how much detail is logged/printed.
# - "minimal": Only errors and campaign summary
# - "normal": Major steps (startup, pool building, campaign end)
# - "verbose": Everything including individual injections
#
# The specific behavior of each level is defined in fi/config/log_levels.py
# where you can customize what events appear at each level.
LOG_LEVEL = "normal" 


# -----------------------------------------------------------------------------
# Area / time profile defaults
# -----------------------------------------------------------------------------

# Name of the default area profile to use when the user does not specify one.
DEFAULT_AREA_PROFILE = "device"

# Default arguments for area profiles (empty string = no default args)
DEFAULT_AREA_ARGS = ""

# Name of the default time profile.
DEFAULT_TIME_PROFILE = "uniform"

# Default arguments for time profiles (empty string = no default args)
DEFAULT_TIME_ARGS = "rate_hz=1"


# -----------------------------------------------------------------------------
# ACME / mapping defaults
# -----------------------------------------------------------------------------

# Default path to the EBD file used by ACME to map regions to configuration
# bits. This file should describe the whole device and is shared across
# modules/pblocks on the same board. The CLI can override this path per run.
DEFAULT_EBD_PATH = "backend/acme/design.ebd"

# ACME cache directory
# Cache location for ACME-expanded configuration bit addresses
# Relative to project root (directory containing fi/)
ACME_CACHE_DIR = "gen/acme"


# =============================================================================
# TargetPool Export
# =============================================================================

# Automatically save generated pools to YAML files for reproducibility
# and debugging. Exported pools can be reused with target_list area profile.
TPOOL_AUTO_SAVE = True

# Primary directory for pool YAML files. Pools are saved here by default.
# This directory is created automatically if it doesn't exist.
TPOOL_OUTPUT_DIR = "gen/tpool"

# Custom name for pool files (None = use timestamp-based naming).
# When None, files are named: YYYYMMDD_HHMMSS_profilename.yaml
# When set, files are named: customname.yaml
TPOOL_OUTPUT_NAME = "last_tpool"

# Additional path to copy pool files to (None = no copy).
# Useful for organizing pools in custom locations or sharing between projects.
# The pool is always saved to TPOOL_OUTPUT_DIR; this provides a convenience copy.
TPOOL_ADDITIONAL_PATH = None

# Control when tpool_size limit is applied during pool building
# 
# When True (default): tpool_size only limits pool size in repeat mode
#   - repeat=True  → Pool building stops at tpool_size
#   - repeat=False → Pool exhausts all targets (ignores tpool_size)
# 
# When False: tpool_size always limits pool size
# 
# Use False when you want strict pool size control regardless of repeat mode.
TPOOL_SIZE_BREAK_REPEAT_ONLY = True


# Disregarding everything else, the absolute max injections cap
# Every other cap will be applied before this one, this is just a safety measure
TPOOL_ABSOLUTE_CAP = 1_000_000

# Default target pool size for repeat mode when no explicit tpool_size provided
TPOOL_DEFAULT_SIZE = 200


# =============================================================================
# GPIO Configuration for Register Injection
# =============================================================================

# GPIO is AUTO-ENABLED when REG targets exist in the target pool.
# This setting forces GPIO to remain disabled even when REG targets are detected.
# Use this for testing campaigns without GPIO hardware.
INJECTION_GPIO_FORCE_DISABLED = False

# Single GPIO pin for serial register ID transmission
INJECTION_GPIO_PIN = 17

# Idle value sent when no injection is active (register IDs start at 1)
INJECTION_GPIO_IDLE_ID = 0

# Bit width for register ID transmission (8 bits supports IDs 1-255)
INJECTION_GPIO_REG_ID_WIDTH = 8

# =============================================================================
# Console Settings (for interactive SEM console)
# =============================================================================

# Header style for console display
HEADER_STYLE_DEFAULT = "simple"

# Show available commands on console startup
SHOW_CONSOLE_COMMANDS_DEFAULT = True

# Show SEM cheatsheet on console startup
SHOW_SEM_CHEATSHEET_DEFAULT = True

# Show start mode after connecting
SHOW_START_MODE_DEFAULT = True

# =============================================================================
# Benchmark Synchronization
# =============================================================================

# Enable file-based synchronization with external benchmarks
# When enabled, FI waits for signal file to appear before starting and stops
# if the file is removed during execution.
BENCHMARK_SYNC_ENABLED = False

# Path to signal file for benchmark synchronization
# The FI system waits for this file to exist before starting. If the file
# is removed during campaign execution, FI stops gracefully.
BENCHMARK_SYNC_FILE = None

# Time interval between signal file checks (seconds)
# The FI system periodically checks if the signal file still exists.
# This setting controls the time-based checking frequency.
BENCHMARK_CHECK_INTERVAL_S = 1.0

# Injection count between signal file checks
# The FI system checks the signal file after this many injections.
# Works in combination with time-based checking (whichever comes first).
BENCHMARK_CHECK_EVERY_N_INJECTIONS = 100

# Timeout waiting for signal file to appear (seconds)
# Maximum time to wait for the benchmark to signal readiness.
# None = wait forever.
BENCHMARK_SYNC_TIMEOUT = None
