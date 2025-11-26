# =============================================================================
# FATORI-V • FI Profiles Area
# File: modules.py
# -----------------------------------------------------------------------------
# Module-based injection with two-level selection and ratio control.
#=============================================================================

from typing import Dict, List, Any

from fi.profiles.area.base import AreaProfileBase
from fi.profiles.area.common.module_selection import ModuleSelector
from fi.profiles.area.common.ratio_utils import RatioSelector
from fi.targets.pool import TargetPool
from fi.targets.types import TargetSpec, TargetKind
from fi.backend.acme.decoder import expand_pblock_to_config_bits


# -----------------------------------------------------------------------------
# Plugin metadata
# -----------------------------------------------------------------------------

PROFILE_KIND = "area"
PROFILE_NAME = "modules"


def describe() -> str:
    """
    Return human-readable description of this profile.
    
    Returns:
        Description string for help/documentation
    """
    return "Inject into specified modules with configurable selection strategy and ratio"


def default_args() -> Dict[str, Any]:
    """
    Return default argument values for this profile.
    
    Returns:
        Dict of default arguments
    """
    return {
        "include": "",          # Comma-separated module names, empty=all
        "exclude": "",          # Comma-separated exclusions
        "mode": "round_robin",  # sequential, round_robin, random, weighted
        "ratio": 0.5,           # 0.0=all logic, 1.0=all reg
        "repetition": False,    # Allow repeating targets
        "weights": "",          # For weighted mode: "alu:3,lsu:1"
        "seed": None,           # Override seed
        "pool_size": None,      # Optional limit on pool size
    }


def make_profile(args: Dict[str, Any], *, global_seed, settings) -> AreaProfileBase:
    """
    Factory function to create profile instance.
    
    Args:
        args: Argument dict (CLI args merged with defaults)
        global_seed: Master seed for reproducibility (or None)
        settings: fi_settings module
    
    Returns:
        ModulesAreaProfile instance
    """
    merged = default_args()
    merged.update(args)
    return ModulesAreaProfile(
        name=PROFILE_NAME,
        args=merged,
        global_seed=global_seed
    )


# -----------------------------------------------------------------------------
# Profile implementation
# -----------------------------------------------------------------------------

class ModulesAreaProfile(AreaProfileBase):
    """
    Area profile for module-based injection.
    
    This profile implements sophisticated two-level target selection:
    
    Level 1 (Module Selection):
        - Select which module to inject into
        - Modes: sequential, round_robin, random, weighted
        - Support for include/exclude filtering
    
    Level 2 (Target Selection within Module):
        - Select register or logic target based on ratio
        - ratio=0.0: all logic (CONFIG targets)
        - ratio=1.0: all registers (REG targets)
        - ratio=0.5: 50/50 probabilistic mix
    
    Features:
        - Include/exclude module filtering
        - Multiple module selection strategies
        - Probabilistic reg/logic ratio
        - Optional target repetition
        - Pool size limiting
        - Weighted module selection
    """
    
    def build_pool(self, system_dict, board_name: str, ebd_path: str) -> TargetPool:
        """
        Build TargetPool for selected modules.
        
        High-level algorithm:
        1. Get board dictionary from SystemDict
        2. Select modules based on include/exclude filters
        3. Build complete target library for each module (regs + logic via ACME)
        4. Apply two-level selection strategy to build final pool
        
        Args:
            system_dict: SystemDict with board dictionaries
            board_name: Resolved board name
            ebd_path: Path to EBD file
        
        Returns:
            TargetPool with targets in injection order
        """
        # Get board dict
        if board_name not in system_dict.boards:
            raise ValueError(f"Board '{board_name}' not in SystemDict")
        
        board_dict = system_dict.boards[board_name]
        
        # Select modules based on include/exclude filters
        selected_modules = self._select_modules(board_dict)
        
        # Build complete target library for each module
        module_targets = self._build_module_targets(
            board_dict,
            selected_modules,
            board_name,
            ebd_path
        )
        
        # Apply two-level selection strategy to build final pool
        pool = self._apply_selection_strategy(module_targets, selected_modules)
        
        # Log pool building results
        stats = pool.get_stats()
        # log_pool_built(stats, profile_name=PROFILE_NAME)
        
        return pool
    
    def _select_modules(self, board_dict) -> List[str]:
        """
        Select modules based on include/exclude arguments.
        
        Logic:
        1. Parse include list (empty means all modules)
        2. Parse exclude list
        3. Apply both filters
        4. Validate at least one module remains
        
        Args:
            board_dict: BoardDict with available modules
        
        Returns:
            List of selected module names
        
        Raises:
            ValueError: If no modules selected after filtering
        """
        all_modules = list(board_dict.modules.keys())
        
        # Parse include list (comma-separated, empty means all)
        include_str = self.args.get("include", "")
        if include_str:
            include = [m.strip() for m in include_str.split(",") if m.strip()]
        else:
            include = all_modules  # Empty include means all modules
        
        # Parse exclude list (comma-separated)
        exclude_str = self.args.get("exclude", "")
        if exclude_str:
            exclude = {m.strip() for m in exclude_str.split(",") if m.strip()}
        else:
            exclude = set()
        
        # Apply both filters: in include list AND not in exclude list
        selected = [m for m in include if m in all_modules and m not in exclude]
        
        if not selected:
            raise ValueError(
                f"No modules selected after filtering. "
                f"Available modules: {all_modules}, "
                f"Include filter: {include}, "
                f"Exclude filter: {exclude}"
            )
        
        return selected
    
    def _build_module_targets(
        self,
        board_dict,
        modules: List[str],
        board_name: str,
        ebd_path: str
    ) -> Dict[str, Dict[str, List[TargetSpec]]]:
        """
        Build complete target library for each module.
        
        For each module:
        1. Build all register targets from module.registers list
        2. Build all logic targets via ACME expansion of module pblock
        3. Store in {"regs": [...], "logic": [...]} structure
        
        Args:
            board_dict: BoardDict with module information
            modules: List of module names to build targets for
            board_name: Board name for ACME
            ebd_path: EBD file path for ACME
        
        Returns:
            Dict mapping module_name to {"regs": [...], "logic": [...]}
        """
        library = {}
        
        for module_name in modules:
            module_info = board_dict.modules[module_name]
            
            # Build register targets from module.registers list
            reg_targets = []
            for reg_id in module_info.registers:
                # Look up register name from board_dict.registers
                reg_name = self._find_register_name(board_dict, reg_id)
                
                reg_targets.append(TargetSpec(
                    kind=TargetKind.REG,
                    module_name=module_name,
                    reg_id=reg_id,
                    reg_name=reg_name,
                    source=f"profile:{PROFILE_NAME}"
                ))
            
            # Build logic targets via ACME expansion of pblock
            pblock = module_info.pblock
            addresses = expand_pblock_to_config_bits(
                region=pblock.region,
                board_name=board_name,
                ebd_path=ebd_path
            )
            
            logic_targets = []
            for addr in addresses:
                logic_targets.append(TargetSpec(
                    kind=TargetKind.CONFIG,
                    module_name=module_name,
                    config_address=addr,
                    pblock_name=pblock.name,
                    source=f"profile:{PROFILE_NAME}"
                ))
            
            # Store in library
            library[module_name] = {
                "regs": reg_targets,
                "logic": logic_targets
            }
        
        return library
    
    def _find_register_name(self, board_dict, reg_id: int) -> str:
        """
        Find register name from reg_id.
        
        Searches board_dict.registers for matching reg_id and returns
        the associated name. Falls back to "reg_{reg_id}" if not found.
        
        Args:
            board_dict: BoardDict with registers list
            reg_id: Register ID to look up
        
        Returns:
            Register name or "reg_{reg_id}" if not found
        """
        for reg in board_dict.registers:
            if reg.reg_id == reg_id:
                return reg.name
        return f"reg_{reg_id}"
    
    def _apply_selection_strategy(
        self,
        module_targets: Dict,
        modules: List[str]
    ) -> TargetPool:
        """
        Apply two-level selection strategy to build final pool.
        
        Two-level selection:
        1. Select module (according to mode: round_robin/sequential/random/weighted)
        2. Select target within module (according to ratio: reg vs logic probability)
        
        Continues until:
        - pool_size limit reached (if specified)
        - all modules exhausted (if repetition=False)
        - safety iteration limit reached (10000 or pool_size)
        
        Args:
            module_targets: Target library from _build_module_targets()
            modules: List of module names
        
        Returns:
            TargetPool with targets in injection order
        """
        pool = TargetPool()
        
        # Parse weights for weighted mode
        weights = self._parse_weights()
        
        # Create level-1 selector (module selection)
        module_selector = ModuleSelector(
            modules=modules,
            mode=self.args.get("mode", "round_robin"),
            weights=weights,
            rng=self.rng
        )
        
        # Create level-2 selector (reg/logic ratio within module)
        ratio_selector = RatioSelector(
            ratio=float(self.args.get("ratio", 0.5)),
            rng=self.rng
        )
        
        # Get pool building parameters
        pool_size_limit = self.args.get("pool_size")
        allow_repetition = self.args.get("repetition", False)
        
        # Track used targets if repetition not allowed
        used_targets = {m: set() for m in modules} if not allow_repetition else None
        
        # Build pool iteratively
        iteration = 0
        max_iterations = pool_size_limit or 10000  # Safety limit
        
        while iteration < max_iterations:
            iteration += 1
            
            # Level 1: Select module
            module = module_selector.next_module()
            
            # Level 2: Select target within module (according to ratio)
            try:
                target = self._select_target_from_module(
                    module,
                    module_targets[module],
                    ratio_selector,
                    used_targets[module] if used_targets else None
                )
            except ValueError:
                # Module exhausted (only possible if repetition=False)
                # Continue to try other modules
                continue
            
            pool.add(target)
            
            # Check pool size limit
            if pool_size_limit and len(pool) >= pool_size_limit:
                break
            
            # Check if all modules exhausted (only relevant if repetition=False)
            if not allow_repetition:
                all_exhausted = all(
                    self._module_exhausted(module_targets[m], used_targets[m])
                    for m in modules
                )
                if all_exhausted:
                    break
        
        return pool
    
    def _select_target_from_module(
        self,
        module_name: str,
        targets: Dict[str, List[TargetSpec]],
        ratio_selector: RatioSelector,
        used_targets: set = None
    ) -> TargetSpec:
        """
        Select one target from module according to ratio.
        
        Steps:
        1. Get available targets (excluding used targets if tracking)
        2. Decide reg vs logic based on ratio
        3. Select randomly from appropriate pool
        4. Mark as used (if tracking)
        
        Args:
            module_name: Module name (for error messages)
            targets: {"regs": [...], "logic": [...]} for this module
            ratio_selector: RatioSelector for reg/logic decision
            used_targets: Set of used target IDs (or None if repetition allowed)
        
        Returns:
            Selected TargetSpec
        
        Raises:
            ValueError: If module is exhausted (no available targets)
        """
        # Get available targets (copy to avoid modifying library)
        reg_pool = targets["regs"].copy()
        logic_pool = targets["logic"].copy()
        
        # Remove used targets if tracking
        if used_targets is not None:
            reg_pool = [t for t in reg_pool if id(t) not in used_targets]
            logic_pool = [t for t in logic_pool if id(t) not in used_targets]
        
        # Check if module exhausted
        if not reg_pool and not logic_pool:
            raise ValueError(f"Module {module_name} exhausted")
        
        # Decide reg vs logic based on ratio
        if ratio_selector.should_select_reg():
            # Prefer register, fall back to logic if no regs available
            pool = reg_pool if reg_pool else logic_pool
        else:
            # Prefer logic, fall back to register if no logic available
            pool = logic_pool if logic_pool else reg_pool
        
        if not pool:
            # Should never happen due to exhaustion check above
            raise ValueError(f"Module {module_name} has no available targets")
        
        # Select randomly from pool
        target = self.rng.choice(pool)
        
        # Mark as used if tracking
        if used_targets is not None:
            used_targets.add(id(target))
        
        return target
    
    def _module_exhausted(self, targets: Dict, used: set) -> bool:
        """
        Check if module is exhausted (all targets used).
        
        Args:
            targets: {"regs": [...], "logic": [...]} for module
            used: Set of used target IDs
        
        Returns:
            True if no targets remain available
        """
        available = (
            [t for t in targets["regs"] if id(t) not in used] +
            [t for t in targets["logic"] if id(t) not in used]
        )
        return len(available) == 0
    
    def _parse_weights(self) -> Dict[str, float]:
        """
        Parse weights from args for weighted mode.
        
        Parses string like "alu:3,lsu:1,decoder:2" into
        {"alu": 3.0, "lsu": 1.0, "decoder": 2.0}
        
        Returns:
            Dict mapping module name to weight (empty if not weighted mode)
        """
        weights_str = self.args.get("weights", "")
        if not weights_str:
            return {}
        
        weights = {}
        for pair in weights_str.split(","):
            if ":" not in pair:
                continue
            module, weight = pair.split(":", 1)
            try:
                weights[module.strip()] = float(weight.strip())
            except ValueError:
                # Ignore invalid weight specifications
                pass
        
        return weights