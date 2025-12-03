# =============================================================================
# FATORI-V • FI Area Profile Loader
# File: profiles/area/common/loader.py
# -----------------------------------------------------------------------------
# Resolves area profile names into live profile objects.
#=============================================================================

from __future__ import annotations

import importlib
from typing import Any, Dict

from fi import fi_settings as settings
from fi.core.config.config import Config
from fi.core.config.seed_manager import (
    get_effective_seed,
    derive_area_seed,
)


def _parse_arg_csv(csv: str) -> Dict[str, str]:
    """
    Parse a simple comma-separated "k=v" list into a dictionary.

    Examples:
        "path=addresses.txt,order=sequential"
        "ratio=0.5,modules=3"

    Whitespace around keys and values is stripped. Empty strings map to {}.
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
        # This allows: targets=controller+lsu to become targets="controller,lsu"
        if '+' in value:
            value = value.replace('+', ',')

        if not key:
            # Ignore malformed pieces without a key
            continue
        result[key] = value
    return result


def _load_profile_module(name: str):
    """
    Import the Python module that implements an area profile.

    name:
        logical profile name (e.g. "device", "modules", "target_list").

    The module is expected at:
        fi.profiles.area.<name>
    """
    if not name:
        raise ValueError("Area profile name is empty.")

    module_path = f"fi.profiles.area.{name}"
    return importlib.import_module(module_path)


def load_area_profile(cfg: Config):
    """
    Load and construct the area profile selected in the Config.

    The resulting object is expected to expose at least:
        - next_target() -> TargetSpec | None
        - describe()    -> str
    
    Seed resolution:
    1. Explicit --area-seed takes priority
    2. Derived from --global-seed if present
    3. No seed (profile uses random)
    
    Args:
        cfg: Config object with profile settings
        
    Returns:
        Loaded area profile instance
    """
    name = cfg.area_profile
    args_csv = cfg.area_args or ""
    
    # Load profile module
    module = _load_profile_module(name)

    # Sanity check the advertised kind, when present
    advertised_kind = getattr(module, "PROFILE_KIND", None)
    if advertised_kind is not None and advertised_kind != "area":
        raise RuntimeError(
            f"Profile '{name}' claims kind '{advertised_kind}' "
            f"but was requested as 'area'."
        )

    # Parse arguments string into a dict
    args_dict = _parse_arg_csv(args_csv)

    # Every profile module must expose make_profile
    factory = getattr(module, "make_profile", None)
    if factory is None:
        raise RuntimeError(
            f"Profile module 'fi.profiles.area.{name}' does not "
            f"define make_profile(...)."
        )

    # Derive effective seed for area profile
    effective_seed = get_effective_seed(
        explicit=cfg.area_seed,
        global_seed=cfg.global_seed,
        derive_fn=derive_area_seed
    )

    # Build profile instance
    profile = factory(
        args=args_dict,
        global_seed=effective_seed,
        settings=settings,
    )
    
    return profile