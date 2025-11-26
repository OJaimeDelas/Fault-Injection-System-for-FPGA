# =============================================================================
# FATORI-V • FI Profiles Area
# File: module_selection.py
# -----------------------------------------------------------------------------
# Module selection strategies for area profiles.
#=============================================================================

from typing import List, Dict, Optional
import random


class ModuleSelector:
    """
    Handles module selection strategies for area profiles.
    
    Supports multiple selection modes:
    - sequential: alu, alu, ..., lsu, lsu, ... (exhausts each module)
    - round_robin: alu, lsu, decoder, alu, lsu, ... (cycles through modules)
    - random: Random module each time (uniform)
    - weighted: Random with configurable weights per module
    
    Attributes:
        modules: List of module names to select from
        mode: Selection strategy ("sequential", "round_robin", "random", "weighted")
        weights: Weight dict for weighted mode (module_name -> weight)
        rng: Random number generator (for reproducibility)
    """
    
    def __init__(
        self,
        modules: List[str],
        mode: str = "round_robin",
        weights: Optional[Dict[str, float]] = None,
        rng: Optional[random.Random] = None
    ):
        """
        Initialize module selector.
        
        Args:
            modules: List of module names to select from
            mode: Selection mode (sequential, round_robin, random, weighted)
            weights: Weight dict for weighted mode (module_name -> weight)
            rng: Random number generator (for reproducibility)
        """
        self.modules = modules
        self.mode = mode
        self.weights = weights or {}
        self.rng = rng or random.Random()
        self._position = 0
    
    def next_module(self) -> str:
        """
        Get next module according to selection strategy.
        
        Returns:
            Module name
        
        Raises:
            ValueError: If mode is unknown
        """
        if self.mode == "sequential":
            return self._next_sequential()
        elif self.mode == "round_robin":
            return self._next_round_robin()
        elif self.mode == "random":
            return self._next_random()
        elif self.mode == "weighted":
            return self._next_weighted()
        else:
            raise ValueError(f"Unknown module selection mode: {self.mode}")
    
    def _next_sequential(self) -> str:
        """
        Sequential selection: alu, alu, ..., lsu, lsu, ...
        
        Stays on same module until caller decides to advance (e.g., when
        module is exhausted). Caller must call advance_position() or
        manage position externally.
        
        Returns:
            Current module name
        """
        return self.modules[self._position % len(self.modules)]
    
    def _next_round_robin(self) -> str:
        """
        Round-robin selection: alu, lsu, decoder, alu, lsu, ...
        
        Cycles through modules one at a time, advancing position after
        each call. Wraps around when reaching end of list.
        
        Returns:
            Next module name in sequence
        """
        module = self.modules[self._position % len(self.modules)]
        self._position += 1
        return module
    
    def _next_random(self) -> str:
        """
        Uniformly random module selection.
        
        Each call independently selects a random module with equal
        probability. Uses the profile's RNG for reproducibility.
        
        Returns:
            Randomly selected module name
        """
        return self.rng.choice(self.modules)
    
    def _next_weighted(self) -> str:
        """
        Weighted random selection.
        
        Modules selected with probability proportional to their weights.
        If no weights provided for a module, defaults to weight of 1.0.
        If no weights provided at all, falls back to uniform random.
        
        Returns:
            Randomly selected module name (according to weights)
        """
        if not self.weights:
            # No weights provided, fall back to uniform random
            return self._next_random()
        
        # Normalize weights to probabilities
        total = sum(self.weights.get(m, 1.0) for m in self.modules)
        probs = [self.weights.get(m, 1.0) / total for m in self.modules]
        
        # Select module according to weighted probabilities
        return self.rng.choices(self.modules, weights=probs)[0]
    
    def advance_position(self):
        """
        Manually advance position counter.
        
        Used by sequential mode when caller determines module is exhausted
        and wants to move to next module.
        """
        self._position += 1