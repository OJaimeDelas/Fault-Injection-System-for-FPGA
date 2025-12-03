# =============================================================================
# FATORI-V • FI Time Profile Loader
# File: profiles/time/common/loader.py
# -----------------------------------------------------------------------------
# Resolves time profile names into live profile objects.
#=============================================================================

from __future__ import annotations

import importlib
from typing import Any, Dict

from fi import fi_settings as settings
from fi.core.config.config import Config
from fi.core.config.seed_manager import (
    get_effective_seed,
    derive_time_seed,
)


def _parse_arg_csv(csv: str) -> Dict[str, str]:
    """
    Parse a simple comma-separated "k=v" list into a dictionary.
    
    Supports list values using + as separator (e.g., targets=a+b+c).
    
    Examples:
        "path=addresses.txt,order=sequential"
        "ratio=0.5,modules=3"
        "targets=controller+lsu+if_stage,ratio=0.5"
    
    Whitespace around keys and values is stripped. Empty strings map to {}.
    List values use + separator, which gets converted back to comma in the value.
    """
    result: Dict[str, str] = {}
    if not csv:
        return result
    
    parts = csv.split(",")
    for raw in parts:
        item = raw.strip()
        if not item:
            # Skip empty segments
            continue
        if "=" not in item:
            # Bare flag: treat as key with value "true"
            result[item] = "true"
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Convert + separator back to comma for list values
        if '+' in value:
            value = value.replace('+', ',')

        if not key:
            # Ignore malformed pieces without a key
            continue
        result[key] = value
    return result


def _load_profile_module(name: str):
    """
    Import the Python module that implements a time profile.

    name:
        logical profile name (e.g. "uniform", "poisson", "ramp").

    The module is expected at:
        fi.profiles.time.<name>
    """
    if not name:
        raise ValueError("Time profile name is empty.")

    module_path = f"fi.profiles.time.{name}"
    return importlib.import_module(module_path)


def load_time_profile(cfg: Config):
    """
    Load and construct the time profile selected in the Config.

    The resulting object is expected to expose:
        - run(controller) -> None
    where `controller` is an InjectionController instance.
    
    Seed resolution:
    1. Explicit --time-seed takes priority
    2. Derived from --global-seed if present
    3. No seed (profile uses random)
    
    Args:
        cfg: Config object with profile settings
        
    Returns:
        Loaded time profile instance
    """
    name = cfg.time_profile
    args_csv = cfg.time_args or ""
    
    # Load profile module
    module = _load_profile_module(name)

    # Sanity check the advertised kind, when present
    advertised_kind = getattr(module, "PROFILE_KIND", None)
    if advertised_kind is not None and advertised_kind != "time":
        raise RuntimeError(
            f"Profile '{name}' claims kind '{advertised_kind}' "
            f"but was requested as 'time'."
        )

    # Parse arguments string into a dict
    args_dict = _parse_arg_csv(args_csv)

    # Every profile module must expose make_profile
    factory = getattr(module, "make_profile", None)
    if factory is None:
        raise RuntimeError(
            f"Profile module 'fi.profiles.time.{name}' does not "
            f"define make_profile(...)."
        )

    # Derive effective seed for time profile
    effective_seed = get_effective_seed(
        explicit=cfg.time_seed,
        global_seed=cfg.global_seed,
        derive_fn=derive_time_seed
    )

    # Build profile instance
    profile = factory(
        args=args_dict,
        global_seed=effective_seed,
        settings=settings,
    )
    
    return profile