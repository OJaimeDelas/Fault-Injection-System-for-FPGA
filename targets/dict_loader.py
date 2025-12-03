# =============================================================================
# FATORI-V • FI Targets
# File: dict_loader.py
# -----------------------------------------------------------------------------
# Load and parse system dictionary with minimal format (coordinates + registers).
#=============================================================================

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

from fi.core.logging.events import log_systemdict_loaded, log_error


@dataclass
class TargetInfo:
    """
    Target module information from system dictionary.
    
    A target represents a physical region on the FPGA with associated registers
    for fault injection monitoring. Uses direct physical coordinates (x_lo, y_lo,
    x_hi, y_hi) rather than abstract region names.
    
    Attributes:
        x_lo: Minimum X coordinate (physical tiles)
        y_lo: Minimum Y coordinate (physical tiles)
        x_hi: Maximum X coordinate (physical tiles)
        y_hi: Maximum Y coordinate (physical tiles)
        registers: List of register IDs monitored for this target
        module: Optional RTL module name (e.g., "ibex_controller")
    """
    x_lo: int
    y_lo: int
    x_hi: int
    y_hi: int
    registers: List[int]
    module: Optional[str] = None


@dataclass
class DeviceInfo:
    """
    Device-level configuration parameters.
    
    Provides physical bounds and frame parameters needed for ACME address
    generation and coordinate mapping.
    
    Attributes:
        min_x: Minimum X coordinate of device
        max_x: Maximum X coordinate of device
        min_y: Minimum Y coordinate of device
        max_y: Maximum Y coordinate of device
        wf: Words per frame (device-specific constant)
    """
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    wf: int


@dataclass
class RegisterInfo:
    """
    Register information from system dictionary.
    
    Attributes:
        reg_id: Unique register identifier (integer)
        name: Human-readable register name (e.g., "ctrl_fsm_cs")
        module: Source RTL module (e.g., "ibex_controller")
    """
    reg_id: int
    name: str
    module: str


@dataclass
class BoardDict:
    """
    Dictionary for one board configuration (minimal format).
    
    Contains device parameters, fault injection targets with physical coordinates,
    and complete register mapping. All targets are specified by physical tile
    coordinates rather than abstract region names.
    
    Attributes:
        device: Device-level parameters (bounds, frame config)
        targets: Dict mapping target name to TargetInfo (coordinates + registers)
        registers: Dict mapping register ID to RegisterInfo
    """
    device: DeviceInfo
    targets: Dict[str, TargetInfo]
    registers: Dict[int, RegisterInfo]

    @property
    def full_device_region(self) -> str:
        """
        Generate full device region string in CLOCKREGION format from device bounds.
        
        Converts physical device coordinates (min_x, max_x, min_y, max_y) into
        the CLOCKREGION format expected by ACME decoder.
        
        Returns:
            Region string like "CLOCKREGION_X0Y0:CLOCKREGION_X358Y310"
        
        Example:
            >>> board_dict.full_device_region
            'CLOCKREGION_X0Y0:CLOCKREGION_X358Y310'
        """
        return (
            f"CLOCKREGION_X{self.device.min_x}Y{self.device.min_y}:"
            f"CLOCKREGION_X{self.device.max_x}Y{self.device.max_y}"
        )


@dataclass
class SystemDict:
    """
    Complete system dictionary with per-board configurations.
    
    The system dictionary can describe multiple boards (e.g., basys3, xcku040).
    Each board has its complete hardware description with physical coordinates.
    Board selection happens via CLI argument or auto-detection.
    
    Attributes:
        boards: Dict mapping board name to BoardDict
        source_path: Path to YAML file this was loaded from (optional)
    """
    boards: Dict[str, BoardDict]
    source_path: Optional[str] = None


def load_system_dict(path: str, is_user_path: bool = True) -> SystemDict:
    """
    Load system dictionary from YAML file (minimal format).
    
    Path resolution:
    - If is_user_path=True: Resolve relative to current working directory
    - If is_user_path=False: Resolve relative to fi/ package directory
    
    Expected YAML structure (minimal format with physical coordinates):
```yaml
    xcku040:
      device:
        min_x: 0
        max_x: 358
        min_y: 0
        max_y: 310
        wf: 123
      
      targets:
        controller:
          x_lo: 50
          y_lo: 50
          x_hi: 75
          y_hi: 65
          registers: [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
          module: ibex_controller  # Optional RTL module name
        
        lsu:
          x_lo: 100
          y_lo: 50
          x_hi: 120
          y_hi: 60
          registers: [128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139]
          module: ibex_load_store_unit  # Optional
      
      registers:
        1: {name: "minor_cnt_o", module: "fatori_fault_mgr"}
        7: {name: "mem_resp_intg_err_irq_pending_q", module: "ibex_controller"}
        # ... etc
```
    
    Args:
        path: Path to system dictionary YAML file
        is_user_path: True if path from CLI (relative to CWD), False if default (relative to fi/)
    
    Returns:
        SystemDict with parsed board configurations
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is malformed or missing required fields
    """
    from fi.core.config.path_resolver import resolve_path
    
    path_obj = resolve_path(path, is_user_path)
    
    if not path_obj.exists():
        log_error(f"System dictionary not found: {path_obj}")
        raise FileNotFoundError(f"System dictionary not found: {path_obj}")
    
    # Load YAML
    try:
        with open(path_obj, 'r') as f:
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
        source_path=str(path_obj)
    )
    
    # Log successful loading
    total_targets = sum(len(bd.targets) for bd in boards.values())
    log_systemdict_loaded(
        path=str(path_obj),
        boards=list(boards.keys()),
        total_modules=total_targets
    )
    
    return system_dict


def _parse_board_dict(board_name: str, data: dict) -> BoardDict:
    """
    Parse single board dictionary from YAML data (minimal format).
    
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
    
    # Parse device section (required)
    if 'device' not in data:
        raise ValueError(f"Board '{board_name}' missing 'device' section")
    
    device = _parse_device_info(board_name, data['device'])
    
    # Parse targets section
    targets_data = data.get('targets', {})
    if not isinstance(targets_data, dict):
        raise ValueError(f"Board '{board_name}' targets must be a dict")
    
    targets = {}
    for target_name, target_data in targets_data.items():
        try:
            targets[target_name] = _parse_target_info(target_name, target_data)
        except Exception as e:
            raise ValueError(f"Error parsing target '{target_name}': {e}")
    
    # Parse registers section
    registers_data = data.get('registers', {})
    if not isinstance(registers_data, dict):
        raise ValueError(f"Board '{board_name}' registers must be a dict")
    
    registers = {}
    for reg_id, reg_data in registers_data.items():
        try:
            reg_id_int = int(reg_id)
            registers[reg_id_int] = _parse_register_info(reg_id_int, reg_data)
        except Exception as e:
            raise ValueError(f"Error parsing register {reg_id}: {e}")
    
    return BoardDict(
        device=device,
        targets=targets,
        registers=registers
    )


def _parse_device_info(board_name: str, data: dict) -> DeviceInfo:
    """
    Parse device section from YAML data.
    
    Args:
        board_name: Name of the board (for error messages)
        data: Device data from YAML
    
    Returns:
        DeviceInfo with parsed data
    
    Raises:
        ValueError: If required fields missing or malformed
    """
    if not isinstance(data, dict):
        raise ValueError(f"Board '{board_name}' device section must be a dict")
    
    required_fields = ['min_x', 'max_x', 'min_y', 'max_y', 'wf']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Device section missing required field '{field}'")
    
    try:
        return DeviceInfo(
            min_x=int(data['min_x']),
            max_x=int(data['max_x']),
            min_y=int(data['min_y']),
            max_y=int(data['max_y']),
            wf=int(data['wf'])
        )
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid device parameter value: {e}")


def _parse_target_info(target_name: str, data: dict) -> TargetInfo:
    """
    Parse single target info from YAML data.
    
    Args:
        target_name: Name of the target (for error messages)
        data: Target data from YAML
    
    Returns:
        TargetInfo with parsed data
    
    Raises:
        ValueError: If required fields missing or malformed
    """
    if not isinstance(data, dict):
        raise ValueError(f"Target '{target_name}' data must be a dict")
    
    # Required coordinate fields
    required_coords = ['x_lo', 'y_lo', 'x_hi', 'y_hi']
    for field in required_coords:
        if field not in data:
            raise ValueError(f"Target '{target_name}' missing required field '{field}'")
    
    # Required registers field
    if 'registers' not in data:
        raise ValueError(f"Target '{target_name}' missing 'registers' field")
    
    registers_list = data['registers']
    if not isinstance(registers_list, list):
        raise ValueError(f"Target '{target_name}' registers must be a list")
    
    # Optional module field (RTL module name for documentation)
    module_name = data.get('module', None)
    if module_name is not None:
        module_name = str(module_name)
    
    try:
        return TargetInfo(
            x_lo=int(data['x_lo']),
            y_lo=int(data['y_lo']),
            x_hi=int(data['x_hi']),
            y_hi=int(data['y_hi']),
            registers=[int(reg_id) for reg_id in registers_list],
            module=module_name
        )
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid target parameter value: {e}")


def _parse_register_info(reg_id: int, data: dict) -> RegisterInfo:
    """
    Parse single register info from YAML data.
    
    Args:
        reg_id: Register ID (integer key from YAML)
        data: Register data dict with 'name' and 'module'
    
    Returns:
        RegisterInfo with parsed data
    
    Raises:
        ValueError: If required fields missing or malformed
    """
    if not isinstance(data, dict):
        raise ValueError(f"Register {reg_id} data must be a dict")
    
    if 'name' not in data:
        raise ValueError(f"Register {reg_id} missing 'name' field")
    
    if 'module' not in data:
        raise ValueError(f"Register {reg_id} missing 'module' field")
    
    return RegisterInfo(
        reg_id=reg_id,
        name=str(data['name']),
        module=str(data['module'])
    )