# =============================================================================
# FATORI-V • FI Profiles Area
# File: input.py
# -----------------------------------------------------------------------------
# Forwarder for loading external area profiles from custom Python modules.
#=============================================================================

import importlib.util
from pathlib import Path
from typing import Dict, Any

PROFILE_KIND = "area"
PROFILE_NAME = "input"


def describe() -> str:
    """
    Describe this profile's purpose.
    
    Returns:
        Human-readable description string
    """
    return "Load external area profile from custom Python module"


def default_args() -> Dict[str, Any]:
    """
    Default arguments for input profile.
    
    Returns:
        Dict with default argument values
    """
    return {
        "module_path": None,  # Required - path to external .py file
    }


def make_profile(args: Dict[str, Any], *, global_seed, settings):
    """
    Load and validate external area profile module.
    
    This forwarder profile allows users to provide custom area profiles
    from outside the fi/profiles/ directory structure. The external module
    is loaded dynamically, validated to ensure it implements the required
    interface, and then its make_profile() function is called.
    
    Args:
        args: Arguments dict, must contain 'module_path' key
        global_seed: Global RNG seed for reproducibility
        settings: FI settings object
    
    Returns:
        Profile instance from external module (must have build_pool method)
    
    Raises:
        ValueError: If module_path missing, file not found, invalid interface
    
    Example:
        >>> # User provides custom profile at /tmp/my_area.py
        >>> args = {"module_path": "/tmp/my_area.py", "size": 100}
        >>> profile = make_profile(args, global_seed=42, settings=settings)
        >>> pool = profile.build_pool(system_dict, board_name, ebd_path)
    """
    module_path = args.get("module_path")
    
    # Validate module_path was provided
    if not module_path:
        raise ValueError(
            "input profile requires 'module_path' argument. "
            "Usage: --area input --area-args 'module_path=/path/to/custom.py'"
        )
    
    # Load the external Python module from file system
    external_module = _load_external_module(module_path)
    
    # Validate module implements required area profile interface
    _validate_area_profile_module(external_module, module_path)
    
    # Forward to external module's make_profile function
    # Pass through all args, global_seed, and settings
    return external_module.make_profile(
        args=args,
        global_seed=global_seed,
        settings=settings
    )

def _load_external_module(module_path: str):
    """
    Load Python module from file path using importlib.
    
    Module paths are always resolved relative to the current working directory
    since they come from user CLI arguments.
    
    Args:
        module_path: Relative or absolute path to .py file
    
    Returns:
        Loaded module object
    
    Raises:
        ValueError: If file not found, not .py extension, or load fails
    """
    from fi.core.config.path_resolver import resolve_user_path
    
    path = resolve_user_path(module_path)
    
    # Check file exists
    if not path.exists():
        raise ValueError(f"Module file not found: {path}")
    
    # Check file extension
    if path.suffix != ".py":
        raise ValueError(f"Module must be .py file: {path}")
    
    # Load using importlib machinery
    try:
        # Create module spec from file location
        spec = importlib.util.spec_from_file_location("custom_area_profile", path)
        
        if spec is None or spec.loader is None:
            raise ValueError(f"Failed to create module spec: {path}")
        
        # Create module object from spec
        module = importlib.util.module_from_spec(spec)
        
        # Execute module code to populate namespace
        spec.loader.exec_module(module)
        
        return module
        
    except Exception as e:
        raise ValueError(f"Failed to load module {path}: {e}")


def _validate_area_profile_module(module, module_path: str):
    """
    Validate external module implements required area profile interface.
    
    Area profiles must provide:
    - PROFILE_KIND = "area"
    - PROFILE_NAME (string)
    - describe() function
    - default_args() function
    - make_profile() function
    
    The returned profile object from make_profile() must have:
    - build_pool(system_dict, board_name, ebd_path) method
    
    Args:
        module: Loaded module object to validate
        module_path: Path to module (for error messages)
    
    Raises:
        ValueError: If module missing required attributes or wrong PROFILE_KIND
    """
    # Check PROFILE_KIND constant exists
    if not hasattr(module, "PROFILE_KIND"):
        raise ValueError(
            f"Module missing PROFILE_KIND constant: {module_path}\n"
            f"Add: PROFILE_KIND = 'area'"
        )
    
    # Check PROFILE_KIND has correct value
    if module.PROFILE_KIND != "area":
        raise ValueError(
            f"Module has PROFILE_KIND='{module.PROFILE_KIND}' "
            f"but expected 'area' for area profile: {module_path}"
        )
    
    # Check required attributes exist
    required = ["PROFILE_NAME", "describe", "default_args", "make_profile"]
    missing = [name for name in required if not hasattr(module, name)]
    
    if missing:
        raise ValueError(
            f"Module missing required attributes: {', '.join(missing)}\n"
            f"Module path: {module_path}\n"
            f"Area profiles must define: {', '.join(required)}"
        )
    
    # All validation passed
    # Note: We don't validate the profile object returned by make_profile()
    # here because that would require calling it. The loader will call
    # make_profile() and any issues will surface when build_pool() is called.