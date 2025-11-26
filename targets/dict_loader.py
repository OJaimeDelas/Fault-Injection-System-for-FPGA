# =============================================================================
# FATORI-V • FI Targets
# File: dict_loader.py
# -----------------------------------------------------------------------------
# Load and parse system dictionary with per-board structure.
#=============================================================================

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

from fi.core.logging.events import log_systemdict_loaded, log_error


@dataclass
class PblockInfo:
    """
    Pblock (physical region) within a module.
    
    Attributes:
        name: Pblock identifier (e.g., "alu_pb")
        region: Clock region coordinates (e.g., "CLOCKREGION_X1Y2:CLOCKREGION_X1Y3")
    """
    name: str
    region: str


@dataclass
class ModuleInfo:
    """
    Module information from system dictionary.
    
    A module represents a logical hardware block (e.g., ALU, LSU, decoder) with:
    - Associated registers (by reg_id)
    - Physical placement (pblock with region coordinates)
    - Human-readable description
    
    Attributes:
        description: Human-readable module description
        registers: List of register IDs that belong to this module
        pblock: Physical block placement information
    """
    description: str
    registers: List[int]
    pblock: PblockInfo


@dataclass
class RegisterInfo:
    """
    Register information from system dictionary.
    
    Attributes:
        reg_id: Unique register identifier (integer)
        name: Human-readable register name (e.g., "alu_out", "lsu_addr")
    """
    reg_id: int
    name: str


@dataclass
class BoardDict:
    """
    Dictionary for one board configuration.
    
    Contains all hardware description for a single FPGA board including:
    - Device-wide region (for full device injection)
    - All registers in the design
    - All modules with their pblocks and register assignments
    
    Attributes:
        full_device_region: Complete device region coordinates
        registers: List of all registers in the design
        modules: Dict mapping module name to ModuleInfo
    """
    full_device_region: str
    registers: List[RegisterInfo]
    modules: Dict[str, ModuleInfo]


@dataclass
class SystemDict:
    """
    Complete system dictionary with per-board configurations.
    
    The system dictionary can describe multiple boards (e.g., basys3, xcku040).
    Each board has its own complete hardware description. Board selection
    happens via CLI argument or auto-detection.
    
    Attributes:
        boards: Dict mapping board name to BoardDict
        source_path: Path to YAML file this was loaded from (optional)
    """
    boards: Dict[str, BoardDict]
    source_path: Optional[str] = None


def load_system_dict(path: str) -> SystemDict:
    """
    Load system dictionary from YAML file.
    
    Expected YAML structure:
```yaml
    basys3:
      full_device_region: "CLOCKREGION_X0Y0:CLOCKREGION_X3Y3"
      registers:
        - reg_id: 0
          name: "alu_out"
        - reg_id: 1
          name: "alu_acc"
      modules:
        alu:
          description: "Arithmetic Logic Unit"
          registers: [0, 1]
          pblock:
            name: "alu_pb"
            region: "CLOCKREGION_X1Y2:CLOCKREGION_X1Y3"
    
    xcku040:
      full_device_region: "..."
      registers: [...]
      modules: {...}
```
    
    Args:
        path: Path to system dictionary YAML file
    
    Returns:
        SystemDict with parsed board configurations
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is malformed or missing required fields
    """
    path = Path(path)
    
    if not path.exists():
        log_error(f"System dictionary not found: {path}")
        raise FileNotFoundError(f"System dictionary not found: {path}")
    
    # Load YAML
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        log_error(f"Failed to parse system dictionary YAML", exc=e)
        raise ValueError(f"Failed to parse system dictionary YAML: {e}")
    
    if not isinstance(data, dict):
        log_error("System dictionary must be a YAML dict at top level")
        raise ValueError("System dictionary must be a YAML dict at top level")
    
    # Parse per-board dictionaries
    boards = {}
    for board_name, board_data in data.items():
        try:
            boards[board_name] = _parse_board_dict(board_name, board_data)
        except Exception as e:
            log_error(f"Error parsing board '{board_name}'", exc=e)
            raise ValueError(f"Error parsing board '{board_name}': {e}")
    
    if not boards:
        log_error("System dictionary contains no boards")
        raise ValueError("System dictionary contains no boards")
    
    system_dict = SystemDict(
        boards=boards,
        source_path=str(path)
    )
    
    # Log successful loading
    total_modules = sum(len(bd.modules) for bd in boards.values())
    log_systemdict_loaded(
        path=str(path),
        boards=list(boards.keys()),
        total_modules=total_modules
    )
    
    return system_dict


def _parse_board_dict(board_name: str, data: dict) -> BoardDict:
    """
    Parse single board dictionary from YAML data.
    
    Args:
        board_name: Name of the board (for error messages)
        data: Board dictionary data from YAML
    
    Returns:
        BoardDict with parsed data
    
    Raises:
        ValueError: If required fields missing or malformed
    """
    if not isinstance(data, dict):
        raise ValueError(f"Board '{board_name}' data must be a dict")
    
    # Extract full_device_region (required)
    if 'full_device_region' not in data:
        raise ValueError(f"Board '{board_name}' missing 'full_device_region'")
    full_device_region = data['full_device_region']
    
    # Parse registers list
    registers_data = data.get('registers', [])
    if not isinstance(registers_data, list):
        raise ValueError(f"Board '{board_name}' registers must be a list")
    
    registers = []
    for reg_data in registers_data:
        if not isinstance(reg_data, dict):
            raise ValueError(f"Register entry must be a dict")
        if 'reg_id' not in reg_data or 'name' not in reg_data:
            raise ValueError(f"Register entry missing 'reg_id' or 'name'")
        
        registers.append(RegisterInfo(
            reg_id=int(reg_data['reg_id']),
            name=str(reg_data['name'])
        ))
    
    # Parse modules dict
    modules_data = data.get('modules', {})
    if not isinstance(modules_data, dict):
        raise ValueError(f"Board '{board_name}' modules must be a dict")
    
    modules = {}
    for module_name, module_data in modules_data.items():
        try:
            modules[module_name] = _parse_module_info(module_name, module_data)
        except Exception as e:
            raise ValueError(f"Error parsing module '{module_name}': {e}")
    
    return BoardDict(
        full_device_region=full_device_region,
        registers=registers,
        modules=modules
    )


def _parse_module_info(module_name: str, data: dict) -> ModuleInfo:
    """
    Parse single module info from YAML data.
    
    Args:
        module_name: Name of the module (for error messages)
        data: Module data from YAML
    
    Returns:
        ModuleInfo with parsed data
    
    Raises:
        ValueError: If required fields missing or malformed
    """
    if not isinstance(data, dict):
        raise ValueError(f"Module '{module_name}' data must be a dict")
    
    # Description (required)
    if 'description' not in data:
        raise ValueError(f"Module '{module_name}' missing 'description'")
    description = str(data['description'])
    
    # Registers list (required, can be empty)
    if 'registers' not in data:
        raise ValueError(f"Module '{module_name}' missing 'registers'")
    registers_list = data['registers']
    if not isinstance(registers_list, list):
        raise ValueError(f"Module '{module_name}' registers must be a list")
    registers = [int(reg_id) for reg_id in registers_list]
    
    # Pblock (required)
    if 'pblock' not in data:
        raise ValueError(f"Module '{module_name}' missing 'pblock'")
    pblock_data = data['pblock']
    if not isinstance(pblock_data, dict):
        raise ValueError(f"Module '{module_name}' pblock must be a dict")
    if 'name' not in pblock_data or 'region' not in pblock_data:
        raise ValueError(f"Module '{module_name}' pblock missing 'name' or 'region'")
    
    pblock = PblockInfo(
        name=str(pblock_data['name']),
        region=str(pblock_data['region'])
    )
    
    return ModuleInfo(
        description=description,
        registers=registers,
        pblock=pblock
    )