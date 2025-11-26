# =============================================================================
# FATORI-V • FI Targets
# File: pool_loader.py
# -----------------------------------------------------------------------------
# Load explicit target pools from YAML files.
#=============================================================================

import yaml
from pathlib import Path
from typing import Optional
import logging

from fi.targets.pool import TargetPool
from fi.targets.types import TargetSpec, TargetKind

logger = logging.getLogger(__name__)


def load_pool_from_file(path: str) -> Optional[TargetPool]:
    """
    Load TargetPool from explicit YAML file.
    
    This function loads pre-built target pools that explicitly list every
    target. It does NOT perform any expansion - all targets must be fully
    specified in the YAML file.
    
    Expected YAML format:
```yaml
    targets:
      - kind: CONFIG
        module_name: "alu"
        config_address: "00001234"
        pblock_name: "alu_pb"
      
      - kind: REG
        module_name: "decoder"
        reg_id: 5
        reg_name: "dec_rec_q"
```
    
    Args:
        path: Path to pool YAML file
    
    Returns:
        TargetPool with targets in file order, or None if file missing/invalid
    
    Notes:
        - Targets are loaded in the order they appear in the file
        - Invalid targets are skipped with warnings (doesn't fail entire load)
        - Missing file returns None (not an error)
        - All targets get source="pool:file"
    
    Example:
        >>> pool = load_pool_from_file("my_targets.yaml")
        >>> if pool is not None:
        ...     print(f"Loaded {len(pool)} targets")
    """
    path = Path(path)
    
    # Missing file is not an error (pools are optional)
    if not path.exists():
        logger.warning(f"Pool file not found: {path}")
        return None
    
    # Parse YAML
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to parse pool file {path}: {e}")
        return None
    
    # Validate structure
    if not isinstance(data, dict):
        logger.error(f"Pool file {path} must be a YAML dict at top level")
        return None
    
    if 'targets' not in data:
        logger.error(f"Pool file {path} missing 'targets' key")
        return None
    
    targets_list = data['targets']
    if not isinstance(targets_list, list):
        logger.error(f"Pool file {path} 'targets' must be a list")
        return None
    
    # Parse each target entry
    pool = TargetPool()
    skipped_count = 0
    
    for i, entry in enumerate(targets_list):
        try:
            target = _parse_target_entry(entry)
            pool.add(target)
        except Exception as e:
            logger.warning(f"Skipping invalid target {i} in {path}: {e}")
            skipped_count += 1
    
    # Log results
    if len(pool) > 0:
        logger.info(f"Loaded {len(pool)} targets from {path}")
        if skipped_count > 0:
            logger.warning(f"Skipped {skipped_count} invalid targets in {path}")
    else:
        logger.error(f"No valid targets found in {path}")
        return None
    
    return pool


def _parse_target_entry(entry: dict) -> TargetSpec:
    """
    Parse single target entry from YAML.
    
    Args:
        entry: Target dictionary from YAML
    
    Returns:
        TargetSpec constructed from entry
    
    Raises:
        ValueError: If entry is invalid or missing required fields
    """
    if not isinstance(entry, dict):
        raise ValueError("Target entry must be a dict")
    
    # Parse kind (required)
    kind_str = entry.get('kind', '').upper()
    if kind_str not in ['CONFIG', 'REG']:
        raise ValueError(f"Invalid or missing 'kind': {kind_str}")
    
    kind = TargetKind[kind_str]
    
    # Parse module_name (required)
    module_name = entry.get('module_name')
    if not module_name:
        raise ValueError("Missing 'module_name' field")
    
    # Parse kind-specific fields
    if kind == TargetKind.CONFIG:
        # CONFIG targets require config_address
        if 'config_address' not in entry:
            raise ValueError("CONFIG target missing 'config_address'")
        
        return TargetSpec(
            kind=kind,
            module_name=module_name,
            config_address=entry['config_address'],
            pblock_name=entry.get('pblock_name'),  # Optional
            source="pool:file"
        )
    
    else:  # REG
        # REG targets require reg_id
        if 'reg_id' not in entry:
            raise ValueError("REG target missing 'reg_id'")
        
        return TargetSpec(
            kind=kind,
            module_name=module_name,
            reg_id=int(entry['reg_id']),
            reg_name=entry.get('reg_name'),  # Optional
            source="pool:file"
        )