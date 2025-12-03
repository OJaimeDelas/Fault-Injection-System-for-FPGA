# =============================================================================
# FATORI-V • FI Core Config
# File: path_resolver.py
# -----------------------------------------------------------------------------
# Path resolution utilities for distinguishing default vs user paths.
#=============================================================================

from pathlib import Path


# Get the fi package directory (where fault_injection.py lives)
# This is computed once at module load time
FI_PACKAGE_DIR = Path(__file__).parent.parent.parent.resolve()


def resolve_default_path(path: str) -> Path:
    """
    Resolve default path relative to fi/ package directory.
    
    Default paths come from fi_settings.py and should always be resolved
    relative to the fi/ directory (where fault_injection.py lives), regardless
    of where the user runs the command from.
    
    Args:
        path: Path string from fi_settings.py (e.g., "core/config/system_dict.yaml")
    
    Returns:
        Absolute Path object
    
    Example:
        >>> # Running from anywhere
        >>> resolve_default_path("core/config/system_dict.yaml")
        PosixPath('/path/to/fi/core/config/system_dict.yaml')
    """
    if Path(path).is_absolute():
        return Path(path)
    return FI_PACKAGE_DIR / path


def resolve_user_path(path: str) -> Path:
    """
    Resolve user path relative to current working directory.
    
    User paths come from CLI arguments and should be resolved relative to
    wherever the user is running the command from. This allows users to use
    relative paths naturally.
    
    Args:
        path: Path string from CLI (e.g., "my_custom_profile.py")
    
    Returns:
        Absolute Path object
    
    Example:
        >>> # User runs from /home/user/experiments/
        >>> resolve_user_path("custom_profile.py")
        PosixPath('/home/user/experiments/custom_profile.py')
    """
    return Path(path).resolve()


def resolve_path(path: str, is_user_provided: bool) -> Path:
    """
    Resolve path based on whether it came from user or defaults.
    
    Args:
        path: Path string
        is_user_provided: True if from CLI, False if from fi_settings.py
    
    Returns:
        Absolute Path object
    """
    if is_user_provided:
        return resolve_user_path(path)
    else:
        return resolve_default_path(path)