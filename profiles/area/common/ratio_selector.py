# =============================================================================
# FATORI-V • FI Profiles Area Common
# File: ratio_selector.py
# -----------------------------------------------------------------------------
# Shared utilities for ratio-aware target selection with repeat support.
#=============================================================================

from typing import List, Optional
import random
from fi import fi_settings

class RatioSelector:
    """
    Ratio-aware target selector supporting repeat mode.
    
    This class manages the selection of CONFIG and REG targets while:
    - Respecting a global ratio constraint (e.g., 0.33 = 1 REG per 2 CONFIG)
    - Supporting repeat mode (allow same target multiple times)
    - Tracking selection counts to maintain ratio
    - Working with any random.Random instance for reproducibility
    
    The selector maintains internal state tracking how many CONFIG vs REG
    targets have been selected, and uses this to decide which kind should
    be selected next to maintain the desired ratio.
    """
    
    def __init__(
        self,
        ratio: float,
        repeat: bool,
        rng,
        target_count: Optional[int] = None,
        cfg = None,
        ratio_strict: bool = False
    ):
        """
        Initialize ratio selector.
        
        Args:
            ratio: Proportion of REG targets (0.0=all CONFIG, 1.0=all REG, 0.5=equal)
            repeat: Allow selecting same target multiple times
            rng: Random number generator (already seeded)
            target_count: Total targets to select (tpool_size from profile args)
            cfg: Config instance with tpool settings (uses fi_settings as fallback)
        """        
        self.ratio = ratio
        self.repeat = repeat
        self.rng = rng
        self.target_count = target_count
        self.cfg = cfg
        self.ratio_strict = ratio_strict
        
        # Track selection counts for ratio enforcement
        self.config_selected = 0
        self.reg_selected = 0
    
    def should_pick_reg(self) -> bool:
        """
        Decide if next target should be REG (True) or CONFIG (False).
        
        Uses current selection counts to maintain global ratio across all targets.
        
        Example with ratio=0.67 (2:1 CONFIG:REG):
            - After 2 CONFIG, 0 REG: should pick REG (maintain 2:1)
            - After 2 CONFIG, 1 REG: should pick CONFIG (maintain 2:1)
        
        Special cases:
            - ratio=1.0: Always pick REG (pure REG mode)
            - ratio=0.0: Always pick CONFIG (pure CONFIG mode)
        """
        # Handle edge cases: pure REG or pure CONFIG modes
        if self.ratio == 1.0:
            return True  # Always pick REG
        if self.ratio == 0.0:
            return False  # Always pick CONFIG
        
        total = self.config_selected + self.reg_selected
        
        # If nothing selected yet, decide based on ratio
        if total == 0:
            # Start with REG if ratio > 0.5, otherwise CONFIG
            return self.ratio > 0.5
        
        # Calculate ideal number of REGs at this point
        ideal_regs = total * self.ratio
        
        # If we're behind on REGs, pick REG next
        return self.reg_selected < ideal_regs
    
    def build_sequential_intermixed_pool(
        self,
        config_targets: List,
        reg_targets: List
    ) -> List:
        """
        Build intermixed pool respecting ratio in sequential pattern.
        
        Creates a deterministic pattern like [CONFIG, CONFIG, REG, CONFIG, CONFIG, REG, ...]
        based on the ratio. Handles exhaustion gracefully when repeat=False.
        
        Args:
            config_targets: List of CONFIG TargetSpecs (in sequential order)
            reg_targets: List of REG TargetSpecs (in sequential order)
        
        Returns:
            List of TargetSpecs in injection order
        
        Algorithm:
            For each position in the pool:
            1. Check if REG or CONFIG should be picked (based on ratio)
            2. Pick next available target of that kind
            3. If that kind exhausted and repeat=False, pick other kind
            4. If repeat=True, cycle back to beginning
            5. Stop when target_count reached or both kinds exhausted
        """
        pool = []
        config_idx = 0
        reg_idx = 0
        
        # Get settings from config with fallback to fi_settings
        if self.cfg:
            break_repeat_only = self.cfg.tpool_size_break_repeat_only
            absolute_cap = self.cfg.tpool_absolute_cap
        else:
            break_repeat_only = fi_settings.TPOOL_SIZE_BREAK_REPEAT_ONLY
            absolute_cap = fi_settings.TPOOL_ABSOLUTE_CAP
        
        # Determine stopping condition based on settings
        if break_repeat_only:
            # Default behavior: tpool_size only applies when repeat=True
            if self.repeat and self.target_count:
                # Repeat mode with explicit limit
                max_iterations = min(self.target_count, absolute_cap)
            elif self.repeat:
                # Repeat mode without limit - use absolute cap
                max_iterations = absolute_cap
            else:
                # Non-repeat mode - exhaust all targets (ignore target_count)
                # Only apply absolute_cap as safety measure if total exceeds it
                total_available = len(config_targets) + len(reg_targets)
                if total_available > absolute_cap:
                    # Safety cap prevents extremely large pools
                    max_iterations = absolute_cap
                else:
                    # Allow full exhaustion within reasonable limits
                    max_iterations = total_available
        else:
            # Alternative behavior: tpool_size always applies
            if self.target_count:
                # Use explicit target_count limit regardless of repeat mode
                max_iterations = min(self.target_count, absolute_cap)
            elif self.repeat:
                # Repeat mode without limit - use absolute cap
                max_iterations = absolute_cap
            else:
                # Non-repeat without limit - exhaust all targets
                # Only apply absolute_cap as safety measure if total exceeds it
                total_available = len(config_targets) + len(reg_targets)
                if total_available > absolute_cap:
                    # Safety cap prevents extremely large pools
                    max_iterations = absolute_cap
                else:
                    # Allow full exhaustion within reasonable limits
                    max_iterations = total_available

        for _ in range(max_iterations):
            # Decide which kind to pick next
            pick_reg = self.should_pick_reg()
            
            if pick_reg:
                # Try to pick REG
                if reg_idx < len(reg_targets):
                    pool.append(reg_targets[reg_idx])
                    reg_idx += 1
                    self.reg_selected += 1
                    
                    # Handle repeat cycling
                    if self.repeat and reg_idx >= len(reg_targets):
                        reg_idx = 0
                        
                elif not self.repeat and config_idx < len(config_targets):
                    # REGs exhausted - fallback to CONFIG if not strict
                    if self.ratio_strict:
                        # Strict mode: stop when minority exhausts
                        break
                    pool.append(config_targets[config_idx])
                    config_idx += 1
                    self.config_selected += 1
                else:
                    # Both exhausted or repeat mode with no targets
                    break
            else:
                # Try to pick CONFIG
                if config_idx < len(config_targets):
                    pool.append(config_targets[config_idx])
                    config_idx += 1
                    self.config_selected += 1
                    
                    # Handle repeat cycling
                    if self.repeat and config_idx >= len(config_targets):
                        config_idx = 0
                        
                elif not self.repeat and reg_idx < len(reg_targets):
                    # CONFIGs exhausted - fallback to REG if not strict
                    if self.ratio_strict:
                        # Strict mode: stop when minority exhausts
                        break
                    pool.append(reg_targets[reg_idx])
                    reg_idx += 1
                    self.reg_selected += 1
                else:
                    # Both exhausted or repeat mode with no targets
                    break
            
            # Stop if both exhausted in non-repeat mode
            if not self.repeat:
                if config_idx >= len(config_targets) and reg_idx >= len(reg_targets):
                    break

        return pool
    
    def build_random_intermixed_pool(
        self,
        config_targets: List,
        reg_targets: List
    ) -> List:
        """
        Build intermixed pool with TRUE random selection (independent sampling).
        
        For each pool position, randomly selects a target from the appropriate
        kind (CONFIG or REG based on ratio). With repeat=True, this is true
        random sampling WITH REPLACEMENT - the same target can be selected
        multiple times, even consecutively.
        
        This is different from sequential mode, which cycles through targets
        in order. Here, each position is an independent random draw.
        
        Args:
            config_targets: List of CONFIG TargetSpecs (not used in order)
            reg_targets: List of REG TargetSpecs (not used in order)
        
        Returns:
            List of TargetSpecs in random injection order respecting ratio
        
        Algorithm:
            For each pool position:
            1. Decide if REG or CONFIG should be picked (based on ratio tracking)
            2. Randomly select from that kind's available targets
            3. With repeat=True: Sample WITH replacement (same target can repeat)
            4. With repeat=False: Sample WITHOUT replacement (remove after selection)
        """
        pool = []
        
        # Get settings from config with fallback to fi_settings
        if self.cfg:
            break_repeat_only = self.cfg.tpool_size_break_repeat_only
            absolute_cap = self.cfg.tpool_absolute_cap
        else:
            break_repeat_only = fi_settings.TPOOL_SIZE_BREAK_REPEAT_ONLY
            absolute_cap = fi_settings.TPOOL_ABSOLUTE_CAP
        
        # Determine max pool size
        if break_repeat_only:
            if self.repeat and self.target_count:
                max_iterations = min(self.target_count, absolute_cap)
            elif self.repeat:
                max_iterations = absolute_cap
            else:
                total_available = len(config_targets) + len(reg_targets)
                max_iterations = min(total_available, absolute_cap)
        else:
            if self.target_count:
                max_iterations = min(self.target_count, absolute_cap)
            elif self.repeat:
                max_iterations = absolute_cap
            else:
                total_available = len(config_targets) + len(reg_targets)
                max_iterations = min(total_available, absolute_cap)
        
        # For repeat=False, track which targets have been used
        if not self.repeat:
            available_config = config_targets.copy()
            available_reg = reg_targets.copy()
        
        for _ in range(max_iterations):
            # Decide which kind to pick next (based on ratio)
            pick_reg = self.should_pick_reg()
            
            if pick_reg:
                # Pick from REG targets
                if self.repeat:
                    # WITH replacement: randomly pick from all REG targets
                    if len(reg_targets) > 0:
                        target = self.rng.choice(reg_targets)
                        pool.append(target)
                        self.reg_selected += 1
                    elif len(config_targets) > 0 and not self.ratio_strict:
                        # Fallback to CONFIG if REGs empty
                        target = self.rng.choice(config_targets)
                        pool.append(target)
                        self.config_selected += 1
                    else:
                        break
                else:
                    # WITHOUT replacement: pick and remove
                    if len(available_reg) > 0:
                        target = self.rng.choice(available_reg)
                        available_reg.remove(target)
                        pool.append(target)
                        self.reg_selected += 1
                    elif len(available_config) > 0 and not self.ratio_strict:
                        # Fallback to CONFIG if REGs exhausted
                        target = self.rng.choice(available_config)
                        available_config.remove(target)
                        pool.append(target)
                        self.config_selected += 1
                    else:
                        break
            else:
                # Pick from CONFIG targets
                if self.repeat:
                    # WITH replacement: randomly pick from all CONFIG targets
                    if len(config_targets) > 0:
                        target = self.rng.choice(config_targets)
                        pool.append(target)
                        self.config_selected += 1
                    elif len(reg_targets) > 0 and not self.ratio_strict:
                        # Fallback to REG if CONFIGs empty
                        target = self.rng.choice(reg_targets)
                        pool.append(target)
                        self.reg_selected += 1
                    else:
                        break
                else:
                    # WITHOUT replacement: pick and remove
                    if len(available_config) > 0:
                        target = self.rng.choice(available_config)
                        available_config.remove(target)
                        pool.append(target)
                        self.config_selected += 1
                    elif len(available_reg) > 0 and not self.ratio_strict:
                        # Fallback to REG if CONFIGs exhausted
                        target = self.rng.choice(available_reg)
                        available_reg.remove(target)
                        pool.append(target)
                        self.reg_selected += 1
                    else:
                        break
            
            # Stop if both kinds exhausted in non-repeat mode
            if not self.repeat:
                if len(available_config) == 0 and len(available_reg) == 0:
                    break
        
        return pool


class WeightedModuleSelector:
    """
    Weighted module selector with balance tracking.
    
    Manages selection of modules based on weights, tracking how many
    times each module has been selected to maintain balance over time.
    Supports round-robin, weighted random, and rebalancing when ratio
    constraints force selection of non-scheduled modules.
    """
    
    def __init__(
        self,
        module_names: List[str],
        weights: List[int],
        rng: random.Random,
        mode: str = "weighted"
    ):
        """
        Initialize weighted module selector.
        
        Args:
            module_names: List of module names to select from
            weights: List of weights (same length as module_names)
            rng: Random number generator
            mode: Selection mode ("round_robin", "weighted", "random")
        """
        self.module_names = module_names
        self.weights = weights
        self.rng = rng
        self.mode = mode
        
        # Track how many times each module has been selected
        self.selection_counts = {name: 0 for name in module_names}
        
        # For round-robin mode
        self.round_robin_index = 0
    
    def get_next_module_scheduled(self) -> str:
        """
        Get the next module that should be selected based on mode/weights.
        
        Returns:
            Module name that should be selected next
        """
        if self.mode == "round_robin":
            # Simple rotation through modules
            module = self.module_names[self.round_robin_index]
            self.round_robin_index = (self.round_robin_index + 1) % len(self.module_names)
            return module
            
        elif self.mode == "weighted":
            # Weighted random selection
            return self.rng.choices(self.module_names, weights=self.weights, k=1)[0]
            
        elif self.mode == "random":
            # Pure random (equal weights)
            return self.rng.choice(self.module_names)
        
        else:
            raise ValueError(f"Unknown module selection mode: {self.mode}")
    
    def record_selection(self, module_name: str):
        """
        Record that a module was selected (for balance tracking).
        
        Args:
            module_name: Name of module that was selected
        """
        self.selection_counts[module_name] += 1
    
    def get_most_underselected(self, available_modules: List[str]) -> str:
        """
        Get the module that has been selected least often relative to its weight.
        
        Used for rebalancing when ratio constraints force non-scheduled selections.
        
        Args:
            available_modules: List of module names to choose from
        
        Returns:
            Module name that is most underselected
        """
        # Calculate selection deficit for each module
        deficits = {}
        total_weight = sum(self.weights)
        
        for i, module in enumerate(self.module_names):
            if module not in available_modules:
                continue
            
            # Calculate ideal number of selections based on weight
            total_selections = sum(self.selection_counts.values())
            if total_selections == 0:
                ideal = 0
            else:
                ideal = (self.weights[i] / total_weight) * total_selections
            
            # Deficit = how far behind this module is
            deficits[module] = ideal - self.selection_counts[module]
        
        # Return module with highest deficit
        return max(deficits.keys(), key=lambda m: deficits[m])