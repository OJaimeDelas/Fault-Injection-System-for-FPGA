# =============================================================================
# FATORI-V • FI Console Styling
# File: console_styling.py
# -----------------------------------------------------------------------------
# ANSI styling functions for colored console output.
#=============================================================================

# ANSI escape codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_FG_CYAN = "\033[36m"
_FG_GREEN = "\033[32m"
_FG_YELLOW = "\033[33m"
_FG_RED = "\033[31m"


def style_title(text: str) -> str:
    """Bold cyan for titles/headers."""
    return f"{_BOLD}{_FG_CYAN}{text}{_RESET}"


def style_hint(text: str) -> str:
    """Yellow for hints and help text."""
    return f"{_FG_YELLOW}{text}{_RESET}"


def style_error(text: str) -> str:
    """Bold red for errors."""
    return f"{_BOLD}{_FG_RED}{text}{_RESET}"


def style_prompt(text: str) -> str:
    """Bold green for input prompts."""
    return f"{_BOLD}{_FG_GREEN}{text}{_RESET}"


def make_section_separator() -> str:
    """Generate section separator using console_settings configuration."""
    from fi.console import console_settings as cs
    return cs.SEPARATOR_CHAR * cs.SEPARATOR_LENGTH