# =============================================================================
# FATORI-V • FI Profiles Area
# File: base.py
# -----------------------------------------------------------------------------
# Base class for area profiles (WHERE to inject).
#=============================================================================

from dataclasses import dataclass
from typing import Dict, Any, Optional
import random

from fi.targets.pool import TargetPool


@dataclass
class AreaProfileBase:
    """
    Base class for area profiles.
    
    Area profiles decide WHERE to inject by building a TargetPool. The pool
    is built upfront with targets in injection order. Each profile gets its
    own RNG for reproducibility.
    
    Attributes:
        name: Profile name (e.g., "modules", "device")
        args: Profile-specific arguments from CLI or defaults
        global_seed: Master seed for reproducibility (or None)
    """
    name: str
    args: Dict[str, Any]
    global_seed: Optional[int] = None
    
    def __post_init__(self):
        """
        Initialize profile after construction.
        
        Creates a profile-specific RNG seeded either from:
        1. Explicit 'seed' in args (highest priority)
        2. Derived from global_seed (if provided)
        3. Random seed (if no seeds provided)
        """
        # Determine effective seed for this profile
        seed = self.args.get('seed') or self._derive_seed(self.global_seed)
        
        # Create profile-specific RNG
        self.rng = random.Random(seed)
    
    def _derive_seed(self, global_seed: Optional[int]) -> int:
        """
        Derive profile-specific seed from global seed.
        
        Uses a deterministic hash to derive a unique seed for this profile
        from the global seed. This ensures reproducibility while allowing
        each profile to have independent randomness.
        
        Args:
            global_seed: Master seed (or None)
        
        Returns:
            Derived seed for this profile
        """
        if global_seed is None:
            # No global seed provided, generate random seed
            return random.randint(0, 2**32 - 1)
        
        # Derive seed deterministically from global seed and profile name
        return hash(("area", self.name, global_seed)) % (2**32)
    
    def build_pool(
        self,
        system_dict,
        board_name: str,
        ebd_path: str
    ) -> TargetPool:
        """
        Build complete TargetPool for injection.
        
        This is the main method that area profiles must implement. It should:
        1. Extract relevant data from system_dict
        2. Generate/expand targets (calling ACME if needed)
        3. Apply selection strategy (module order, ratio, etc.)
        4. Return pool with targets in injection order
        
        Must be implemented by subclasses.
        
        Args:
            system_dict: SystemDict with board dictionaries
            board_name: Resolved board name
            ebd_path: Path to EBD file for ACME
        
        Returns:
            TargetPool ready for injection
        
        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError(
            f"Area profile '{self.name}' must implement build_pool()"
        )
    
    def describe(self) -> str:
        """
        Human-readable description of this profile.
        
        Returns:
            Description string for help/documentation
        """
        return f"Area profile: {self.name}"