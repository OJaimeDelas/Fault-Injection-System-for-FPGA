# =============================================================================
# FATORI-V • FI Targets
# File: target_types.py
# -----------------------------------------------------------------------------
# Type definitions for injection targets (TargetSpec and TargetKind).
#=============================================================================

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TargetKind(Enum):
    """
    Type of injection target.
    
    Every target in the FI system is either a configuration bit (logic)
    or a register. This enum distinguishes between the two at the type level.
    
    Attributes:
        CONFIG: Configuration bit injection (via SEM)
        REG: Register injection (via GPIO/board interface)
    """
    CONFIG = "CONFIG"  # Configuration bit (logic/LUTs/routing)
    REG = "REG"        # Register ID (flip-flops in the design)


@dataclass
class TargetSpec:
    """
    Specification of a single injection target.
    
    All injection targets (configuration bits and registers) reduce to this
    unified structure. The 'kind' field determines which fields are required.
    
    Attributes:
        kind: Type of target (CONFIG or REG)
        module_name: Which module this target belongs to (for logging/stats)
        
        config_address: LFA address string (required for CONFIG targets)
        pblock_name: Pblock name (optional for CONFIG targets)
        
        reg_id: Register identifier (required for REG targets)
        reg_name: Human-readable register name (optional for REG targets)
        
        source: Where this target came from (e.g., "profile:modules", "pool:file")
        tags: Tuple of tags for filtering/grouping (optional)
    
    Validation:
        - CONFIG targets must have config_address
        - REG targets must have reg_id
        - Validation happens in __post_init__
    
    Examples:
        >>> # Configuration bit target
        >>> target = TargetSpec(
        ...     kind=TargetKind.CONFIG,
        ...     module_name="alu",
        ...     config_address="00001234",
        ...     pblock_name="alu_pb",
        ...     source="profile:modules"
        ... )
        
        >>> # Register target
        >>> target = TargetSpec(
        ...     kind=TargetKind.REG,
        ...     module_name="decoder",
        ...     reg_id=5,
        ...     reg_name="dec_rec_q",
        ...     source="profile:modules"
        ... )
    """
    kind: TargetKind
    module_name: str
    
    # For CONFIG kind
    config_address: Optional[str] = None
    pblock_name: Optional[str] = None
    
    # For REG kind
    reg_id: Optional[int] = None
    reg_name: Optional[str] = None
    
    # Metadata
    source: str = "unknown"
    tags: tuple = ()
    
    def __post_init__(self):
        """
        Validate required fields based on target kind.
        
        Ensures that:
        - CONFIG targets have config_address
        - REG targets have reg_id
        
        Raises:
            ValueError: If required field is missing for the target kind
        """
        if self.kind == TargetKind.CONFIG:
            if self.config_address is None:
                raise ValueError(
                    "CONFIG target must have config_address. "
                    f"Target: module_name={self.module_name}"
                )
        elif self.kind == TargetKind.REG:
            if self.reg_id is None:
                raise ValueError(
                    "REG target must have reg_id. "
                    f"Target: module_name={self.module_name}"
                )