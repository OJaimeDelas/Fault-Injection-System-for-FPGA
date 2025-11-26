# =============================================================================
# FATORI-V • FI Profiles Area
# File: ratio_utils.py
# -----------------------------------------------------------------------------
# Ratio-based reg/logic selection for area profiles.
#=============================================================================

from typing import List
import random

from fi.targets.types import TargetSpec


class RatioSelector:
    """
    Handles probabilistic reg/logic selection based on ratio.
    
    The ratio determines the probability of selecting a register vs logic
    target on each selection:
    
    - ratio=0.0: 0% reg (all logic/CONFIG targets)
    - ratio=0.5: 50% reg, 50% logic
    - ratio=1.0: 100% reg (all register targets)
    
    The selection is applied probabilistically on each call to should_select_reg().
    Over many calls, the actual ratio will converge to the configured ratio.
    
    Attributes:
        ratio: Register selection probability (0.0 to 1.0)
        rng: Random number generator (for reproducibility)
    """
    
    def __init__(self, ratio: float, rng: random.Random):
        """
        Initialize ratio selector.
        
        Args:
            ratio: Reg probability (0.0=all logic, 1.0=all reg)
            rng: Random number generator
        
        Raises:
            ValueError: If ratio not in [0.0, 1.0]
        """
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(f"Ratio must be 0.0-1.0, got {ratio}")
        self.ratio = ratio
        self.rng = rng
    
    def should_select_reg(self) -> bool:
        """
        Decide whether to select register or logic.
        
        Uses the configured ratio to probabilistically choose between
        register and logic targets. Each call is independent.
        
        Returns:
            True if should select register, False for logic
        
        Example:
            >>> selector = RatioSelector(ratio=0.3, rng=Random(42))
            >>> # Will return True ~30% of the time
            >>> selector.should_select_reg()
        """
        return self.rng.random() < self.ratio
    
    def select_from_module(
        self,
        reg_targets: List[TargetSpec],
        logic_targets: List[TargetSpec],
        allow_repetition: bool = False
    ) -> TargetSpec:
        """
        Select one target from module according to ratio.
        
        First decides reg vs logic based on ratio, then randomly selects
        one target from that category. If preferred category is empty,
        falls back to other category.
        
        Args:
            reg_targets: Available register targets
            logic_targets: Available logic targets
            allow_repetition: If False, caller must remove used targets
        
        Returns:
            Selected TargetSpec
        
        Raises:
            ValueError: If no targets available in either category
        
        Note:
            When allow_repetition=False, the caller is responsible for
            removing the returned target from the appropriate list before
            calling this method again. This method only performs the
            selection, not the removal.
        """
        # Decide kind based on ratio
        if self.should_select_reg():
            # Prefer register
            pool = reg_targets
            fallback = logic_targets
        else:
            # Prefer logic
            pool = logic_targets
            fallback = reg_targets
        
        # If preferred pool is empty, use fallback
        if not pool:
            pool = fallback
        
        # If both pools are empty, error
        if not pool:
            raise ValueError("No targets available in module")
        
        # Select randomly from pool
        # Note: If allow_repetition=False, caller must manage removal
        return self.rng.choice(pool)