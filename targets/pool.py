# =============================================================================
# FATORI-V • FI Targets Pool
# File: pool.py
# -----------------------------------------------------------------------------
# TargetPool container for ordered sequences of injection targets.
#=============================================================================

from typing import List, Dict, Optional
from fi.targets.types import TargetSpec, TargetKind


class TargetPool:
    """
    Flat list of TargetSpecs in injection order.
    
    A TargetPool is a simple, ordered collection of injection targets. It is
    deliberately passive - it doesn't build itself or make selection decisions.
    Those are the responsibilities of:
    
    - Area profiles: Build pools by adding targets in injection order
    - Time profiles: Consume pools via pop_next()
    - InjectionController: Routes targets to SEM/GPIO
    
    Responsibilities:
        - Store targets sequentially
        - Provide iteration via pop_next()
        - Track statistics (counts by kind/module)
        - Analyze backend requirements (CONFIG vs REG targets)
    
    NOT responsible for:
        - Building itself (area profiles do that)
        - Selection strategy (targets added in correct order already)
        - Routing to backend (InjectionController does that)
    
    Example:
        >>> pool = TargetPool()
        >>> pool.add(target1)
        >>> pool.add(target2)
        >>> 
        >>> # Iterate through pool
        >>> while (target := pool.pop_next()) is not None:
        ...     inject(target)
        >>> 
        >>> # Get statistics
        >>> stats = pool.get_stats()
        >>> print(stats['total'])
        2
    """
    
    def __init__(self):
        """Initialize empty target pool."""
        self._targets: List[TargetSpec] = []
        self._position = 0
    
    def add(self, target: TargetSpec) -> None:
        """
        Add single target to pool.
        
        Targets are added to the end of the pool in the order they will
        be injected. The area profile is responsible for adding targets
        in the correct order.
        
        Args:
            target: TargetSpec to add to pool
        """
        self._targets.append(target)
    
    def add_many(self, targets: List[TargetSpec]) -> None:
        """
        Add multiple targets to pool.
        
        Convenience method for adding a batch of targets at once.
        Equivalent to calling add() for each target.
        
        Args:
            targets: List of TargetSpecs to add to pool
        """
        self._targets.extend(targets)
    
    def pop_next(self) -> Optional[TargetSpec]:
        """
        Get next target in sequence.
        
        This is the main iteration method used by time profiles and the
        injection controller. Each call returns the next target and advances
        the internal position counter.
        
        Returns:
            Next TargetSpec in sequence, or None if pool exhausted
        
        Example:
            >>> target = pool.pop_next()
            >>> if target is not None:
            ...     inject(target)
        """
        if self._position >= len(self._targets):
            return None
        target = self._targets[self._position]
        self._position += 1
        return target
    
    def reset(self) -> None:
        """
        Reset iteration to beginning.
        
        Resets the internal position counter so that the next pop_next()
        call will return the first target again. Useful for repeating
        campaigns or testing.
        """
        self._position = 0
    
    def __len__(self) -> int:
        """
        Total number of targets in pool.
        
        Returns:
            Total count of targets (not remaining count)
        """
        return len(self._targets)
    
    def count_by_kind(self) -> Dict[TargetKind, int]:
        """
        Count targets by kind (CONFIG vs REG).
        
        Returns a dictionary with counts for each TargetKind. All kinds
        are present in the result even if count is zero.
        
        Returns:
            Dict mapping TargetKind to count
        
        Example:
            >>> counts = pool.count_by_kind()
            >>> counts
            {<TargetKind.CONFIG: 'CONFIG'>: 750, <TargetKind.REG: 'REG'>: 250}
        """
        counts = {kind: 0 for kind in TargetKind}
        for target in self._targets:
            counts[target.kind] += 1
        return counts
    
    def count_by_module(self) -> Dict[str, Dict[str, int]]:
        """
        Count targets by module and kind.
        
        Returns a nested dictionary structure:
        - Outer dict: module_name -> inner dict
        - Inner dict: kind string -> count
        
        Returns:
            Dict mapping module name to {kind: count} dict
        
        Example:
            >>> counts = pool.count_by_module()
            >>> counts
            {
                'alu': {'CONFIG': 250, 'REG': 100},
                'lsu': {'CONFIG': 500, 'REG': 150}
            }
        """
        counts = {}
        for target in self._targets:
            if target.module_name not in counts:
                # Initialize with zero counts for both kinds
                counts[target.module_name] = {"CONFIG": 0, "REG": 0}
            counts[target.module_name][target.kind.value] += 1
        return counts
    
    def has_config_targets(self) -> bool:
        """
        Check if pool contains any CONFIG (logic) targets.
        
        Used to determine if SEM backend initialization is needed.
        Returns True if at least one CONFIG target exists.
        
        Returns:
            True if pool contains CONFIG targets, False otherwise
        
        Example:
            >>> if pool.has_config_targets():
            ...     sem_proto = open_sem(cfg, log_ctx)
        """
        for target in self._targets:
            if target.kind == TargetKind.CONFIG:
                return True
        return False
    
    def has_reg_targets(self) -> bool:
        """
        Check if pool contains any REG (register) targets.
        
        Used to determine if GPIO backend initialization is needed.
        Returns True if at least one REG target exists.
        
        Returns:
            True if pool contains REG targets, False otherwise
        
        Example:
            >>> if pool.has_reg_targets():
            ...     board_if = GPIOBoardInterface(cfg)
        """
        for target in self._targets:
            if target.kind == TargetKind.REG:
                return True
        return False
    
    def get_backend_requirements(self) -> Dict[str, bool]:
        """
        Analyze pool to determine which backends are needed.
        
        This method scans the entire pool and returns a dictionary indicating
        which backends (SEM for CONFIG, GPIO for REG) need to be initialized
        based on the target types present in the pool.
        
        This enables conditional backend initialization:
        - Only initialize SEM if CONFIG targets exist
        - Only initialize GPIO if REG targets exist
        - Skip unused backends entirely
        
        Returns:
            Dict with keys "sem" and "gpio", values are bool
        
        Example:
            >>> reqs = pool.get_backend_requirements()
            >>> reqs
            {'sem': True, 'gpio': False}  # CONFIG targets only
            >>> 
            >>> if reqs['sem']:
            ...     sem_proto = open_sem(cfg, log_ctx)
            >>> if reqs['gpio']:
            ...     board_if = GPIOBoardInterface(cfg)
        """
        return {
            "sem": self.has_config_targets(),
            "gpio": self.has_reg_targets()
        }
    
    def get_stats(self) -> Dict:
        """
        Get comprehensive pool statistics.
        
        Returns a dictionary with all available statistics including:
        - Total target count
        - Counts by kind (CONFIG/REG)
        - Counts by module and kind
        - Current iteration position
        - Remaining targets
        
        Returns:
            Dict with comprehensive statistics
        
        Example:
            >>> stats = pool.get_stats()
            >>> stats
            {
                'total': 1000,
                'by_kind': {'CONFIG': 750, 'REG': 250},
                'by_module': {
                    'alu': {'CONFIG': 250, 'REG': 100},
                    'lsu': {'CONFIG': 500, 'REG': 150}
                },
                'position': 0,
                'remaining': 1000
            }
        """
        return {
            "total": len(self),
            "by_kind": {k.value: v for k, v in self.count_by_kind().items()},
            "by_module": self.count_by_module(),
            "position": self._position,
            "remaining": len(self) - self._position
        }