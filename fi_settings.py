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


# -----------------------------------------------------------------------------
# Serial / SEM control
# -----------------------------------------------------------------------------

# Default serial device used to talk to the SEM controller.
DEFAULT_SEM_DEVICE = "/dev/ttyUSB0"

# Default baudrate of the serial link to SEM.
DEFAULT_SEM_BAUDRATE = 1250000

# Clock frequency of the SEM IP core on the FPGA, in hertz.
# This is provided so that timing-related calculations can be made when needed.
SEM_CLOCK_HZ = 100_000_000

# Require successful SEM preflight test before starting campaign
SEM_PREFLIGHT_REQUIRED = True


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
DEFAULT_TIME_ARGS = ""


# -----------------------------------------------------------------------------
# ACME / mapping defaults
# -----------------------------------------------------------------------------

# Default path to the EBD file used by ACME to map regions to configuration
# bits. This file should describe the whole device and is shared across
# modules/pblocks on the same board. The CLI can override this path per run.
DEFAULT_EBD_PATH = "backend/acme/design.ebd"


# =============================================================================
# GPIO Configuration for Register Injection
# =============================================================================

# Enable GPIO control for register injection (False = NoOp/logging only)
INJECTION_GPIO_ENABLED = False

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