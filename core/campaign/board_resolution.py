# =============================================================================
# FATORI-V • FI Engine
# File: board_resolution.py
# -----------------------------------------------------------------------------
# Board name resolution with fallback chain.
#=============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fi.core.config.config import Config
    from fi.targets.dict_loader import SystemDict


def resolve_board_name(cfg: 'Config', system_dict: 'SystemDict') -> str:
    """
    Resolve board name using fallback chain.
    
    The board name determines which hardware configuration from the SystemDict
    to use for this injection campaign. Resolution follows this priority:
    
    1. **CLI explicit**: If user specified --board on command line, use it
    2. **Auto-detect**: If SystemDict has only one board, use that board
    3. **Default fallback**: Use DEFAULT_BOARD_NAME from fi_settings
    4. **Error**: If none of the above work, raise ValueError
    
    Args:
        cfg: Config object with CLI arguments
        system_dict: SystemDict with available board configurations
    
    Returns:
        Resolved board name (guaranteed to exist in system_dict.boards)
    
    Raises:
        ValueError: If board cannot be resolved or requested board not found
    
    Examples:
        >>> # User specified --board basys3
        >>> resolve_board_name(cfg, system_dict)
        'basys3'
        
        >>> # SystemDict has only one board, auto-detect
        >>> resolve_board_name(cfg, system_dict)
        'xcku040'  # The only board in the dict
        
        >>> # Multiple boards, no CLI arg, use default from settings
        >>> resolve_board_name(cfg, system_dict)
        'basys3'  # From DEFAULT_BOARD_NAME
    """
    from fi import fi_settings
    
    # Priority 1: CLI explicit board argument
    if cfg.board_name:
        if cfg.board_name not in system_dict.boards:
            raise ValueError(
                f"Board '{cfg.board_name}' not found in SystemDict. "
                f"Available boards: {list(system_dict.boards.keys())}"
            )
        return cfg.board_name
    
    # Priority 2: Auto-detect if only one board in dict
    if len(system_dict.boards) == 1:
        return list(system_dict.boards.keys())[0]
    
    # Priority 3: Use default from settings
    default = fi_settings.DEFAULT_BOARD_NAME
    if default in system_dict.boards:
        return default
    
    # Priority 4: Cannot resolve - error
    raise ValueError(
        f"Cannot resolve board name. SystemDict has multiple boards but no "
        f"board was specified via --board and the default board "
        f"'{default}' is not in the SystemDict. "
        f"Available boards: {list(system_dict.boards.keys())}"
    )