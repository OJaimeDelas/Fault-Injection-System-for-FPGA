# =============================================================================
# FATORI-V • FI Profiles Area
# File: modules.py
# -----------------------------------------------------------------------------
# Module-based injection with two-level selection and ratio control.
#=============================================================================

from typing import Dict, List, Any, Optional

from fi.profiles.area.base import AreaProfileBase
from fi.profiles.area.common.ratio_selector import RatioSelector, WeightedModuleSelector
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
        "targets": "",              # Comma-separated target names, empty=all
        "exclude": "",              # Comma-separated exclusions
        "module_mode": "weighted",  # round_robin, weighted, random (alias: "module_order")
        "target_mode": "sequential", # sequential, random (alias: "target_order")
        "weights": "",              # For weighted mode: "1-2-3" (dash-separated)
        "ratio": 0.5,              # Proportion of REG targets (0.0-1.0)
        "repeat": True,            # Allow target repetition
        "tpool_size": 200,         # Pool size when repeat=True
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
        - target_modes: sequential, round_robin, random, weighted
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
    
    def build_pool(self, system_dict, board_name: str, ebd_path: str, cfg) -> TargetPool:
        """
        Build TargetPool for selected modules with ratio and repeat support.
        
        High-level algorithm:
        1. Get board dictionary from SystemDict
        2. Select modules based on include/exclude filters
        3. Parse weights for module selection
        4. Build complete target library for each module (ordered by target_mode)
        5. Use two-level selection:
        - First level: Select module (weighted/round-robin/random)
        - Second level: Select target from module (respecting global ratio)
        6. Handle exhaustion and rebalancing
        
        Args:
            system_dict: SystemDict with board dictionaries
            board_name: Resolved board name
            ebd_path: Path to EBD file
            cfg: Config instance with tpool settings
        
        Returns:
            TargetPool with targets in injection order
        """
        # Get board dict
        if board_name not in system_dict.boards:
            raise ValueError(f"Board '{board_name}' not in SystemDict")
        
        board_dict = system_dict.boards[board_name]
        
        # Select modules based on include/exclude filters
        selected_modules = self._select_modules(board_dict)

        
        # Parse weights
        weights = self._parse_weights(selected_modules)
        
        # Build complete target library for each module
        # This pre-orders targets within each module based on target_mode
        module_library = self._build_module_library(
            board_dict,
            selected_modules,
            board_name,
            ebd_path,
            cfg
        )
        
        # Parse ratio and repeat parameters
        ratio = float(self.args.get("ratio", 0.5))
        repeat = self.args.get("repeat", True)
        if isinstance(repeat, str):
            repeat = repeat.lower() in ("true", "1", "yes", "on")
        
        from fi import fi_settings
               
        # Parse tpool_size from args (always parse it, regardless of repeat mode)
        tpool_size_arg = self.args.get("tpool_size")
        if tpool_size_arg is not None:
            tpool_size = int(tpool_size_arg)
        elif repeat:
            # Use default from settings only in repeat mode
            tpool_size = fi_settings.TPOOL_DEFAULT_SIZE
        else:
            tpool_size = None
        
        # Build pool using two-level selection
        pool = self._build_pool_with_two_level_selection(
            module_library=module_library,
            selected_modules=selected_modules,
            weights=weights,
            ratio=ratio,
            repeat=repeat,
            tpool_size=tpool_size,
            cfg=cfg,
            ratio_strict=cfg.ratio_strict if cfg else False
        )
        
        return pool


    def _parse_weights(self, selected_modules: List[str]) -> List[int]:
        """
        Parse weight string into list of integers.
        
        Format: "1-2-3" → [1, 2, 3]
        
        Rules:
        - If more weights than modules: extra weights ignored
        - If fewer weights than modules: remaining modules get weight=1
        - Empty string: all modules get weight=1
        
        Args:
            selected_modules: List of module names
        
        Returns:
            List of weights (same length as selected_modules)
        """
        weights_str = self.args.get("weights", "")
        
        if not weights_str:
            # Empty string: all weights = 1
            return [1] * len(selected_modules)
        
        # Parse dash-separated weights
        weight_parts = weights_str.split("-")
        weights = []
        
        for part in weight_parts:
            try:
                weights.append(int(part.strip()))
            except ValueError:
                raise ValueError(f"Invalid weight value: {part}")
        
        # Pad or trim to match module count
        num_modules = len(selected_modules)
        if len(weights) < num_modules:
            # Fewer weights than modules: pad with 1s
            weights.extend([1] * (num_modules - len(weights)))
        elif len(weights) > num_modules:
            # More weights than modules: trim extras
            weights = weights[:num_modules]
        
        return weights

    def _build_module_library(
        self,
        board_dict,
        selected_modules: List[str],
        board_name: str,
        ebd_path: str,
        cfg
    ) -> Dict[str, Dict[str, List[TargetSpec]]]:
        """
        Build complete target library for each module with ordering.
        
        For each module:
        1. Build all register targets from target.registers list
        2. Build all logic targets via ACME expansion of target coordinates
        3. Order each group based on target_mode (sequential or shuffle)
        4. Store in {"config": [...], "reg": [...]} structure
        
        Args:
            board_dict: BoardDict with target information
            modules: List of module/target names
            board_name: Board name for ACME
            ebd_path: EBD file path for ACME
        
        Returns:
            Dict mapping module_name to {"config": [...], "reg": [...]}
        """
        library = {}
        # Accept both "target_order" and "target_mode" as parameter names (target_order takes priority)
        target_mode = self.args.get("target_order") or self.args.get("target_mode", "sequential")
        
        for module_name in selected_modules:
            target_info = board_dict.targets[module_name]

            
            
            # Build register targets
            reg_targets = []
            for reg_id in target_info.registers:
                reg_name = self._find_register_name(board_dict, reg_id)
                
                reg_targets.append(TargetSpec(
                    kind=TargetKind.REG,
                    module_name=target_info.module or module_name,
                    reg_id=reg_id,
                    reg_name=reg_name,
                    source=f"profile:{PROFILE_NAME}"
                ))
            
            # Build logic targets via ACME
            region_coords = {
                'x_lo': target_info.x_lo,
                'y_lo': target_info.y_lo,
                'x_hi': target_info.x_hi,
                'y_hi': target_info.y_hi
            }
            
            addresses = expand_pblock_to_config_bits(
                region=region_coords,
                board_name=board_name,
                ebd_path=ebd_path,
                use_cache=cfg.acme_cache_enabled,
                cache_dir=cfg.acme_cache_dir
            )
            
            config_targets = []
            for addr in addresses:
                config_targets.append(TargetSpec(
                    kind=TargetKind.CONFIG,
                    module_name=target_info.module or module_name,
                    config_address=addr,
                    pblock_name=module_name,
                    source=f"profile:{PROFILE_NAME}"
                ))
            
            # Apply target_mode ordering to each group
            if target_mode == "random":
                self.rng.shuffle(config_targets)
                self.rng.shuffle(reg_targets)
            # sequential: keep SystemDict order
            
            # Store in library
            library[module_name] = {
                "config": config_targets,
                "reg": reg_targets,
                "config_idx": 0,  # Track consumption position
                "reg_idx": 0
            }
        
        return library

    def _build_pool_with_two_level_selection(
        self,
        module_library: Dict,
        selected_modules: List[str],
        weights: List[int],
        ratio: float,
        repeat: bool,
        tpool_size: Optional[int],
        cfg,
        ratio_strict: bool = False
    ) -> TargetPool:
        """
        Build pool using two-level selection with ratio enforcement.
        
        Two-level algorithm:
        1. First level: Select which module to inject from (weighted/round-robin)
        2. Second level: Select CONFIG or REG from that module (respecting global ratio)
        
        Global ratio is maintained across all modules. When ratio constraint forces
        deviation from module selection schedule, rebalancing is applied.
        
        Args:
            module_library: Pre-built and ordered targets for each module
            selected_modules: List of module names
            weights: List of weights for each module
            ratio: Global REG proportion
            repeat: Allow target repetition
            tpool_size: Target pool size (for repeat mode)
            cfg: Config instance with tpool settings
        
        Returns:
            TargetPool in injection order
        """
        pool = TargetPool()
        
        # Accept both "module_order" and "module_mode" as parameter names (module_order takes priority)
        module_mode = self.args.get("module_order") or self.args.get("module_mode", "weighted")
        module_selector = WeightedModuleSelector(
            module_names=selected_modules,
            weights=weights,
            rng=self.rng,
            mode=module_mode
        )
        
        # Track global ratio
        config_count = 0
        reg_count = 0
        
        # Get settings from config with fallback to fi_settings
        from fi import fi_settings
        if cfg:
            break_repeat_only = cfg.tpool_size_break_repeat_only
            absolute_cap = cfg.tpool_absolute_cap
        else:
            break_repeat_only = fi_settings.TPOOL_SIZE_BREAK_REPEAT_ONLY
            absolute_cap = fi_settings.TPOOL_ABSOLUTE_CAP
        
        # Determine stopping condition based on settings
        if break_repeat_only:
            # Default behavior: tpool_size only applies when repeat=True
            if repeat and tpool_size:
                max_iterations = min(tpool_size, absolute_cap)
            else:
                # Count total available targets
                total_available = sum(
                    len(lib["config"]) + len(lib["reg"])
                    for lib in module_library.values()
                )
                max_iterations = min(total_available, absolute_cap)
        else:
            # Alternative behavior: tpool_size always applies
            if tpool_size:
                max_iterations = min(tpool_size, absolute_cap)
            else:
                # Count total available targets
                total_available = sum(
                    len(lib["config"]) + len(lib["reg"])
                    for lib in module_library.values()
                )
                max_iterations = min(total_available, absolute_cap)
        
        # Build pool
        for iteration in range(max_iterations):
            # Determine if next injection should be REG (based on global ratio)
            # Handle edge cases: pure REG (1.0) or pure CONFIG (0.0) modes
            if ratio == 1.0:
                need_reg = True  # Always pick REG
            elif ratio == 0.0:
                need_reg = False  # Always pick CONFIG
            else:
                total_injections = config_count + reg_count
                if total_injections == 0:
                    # Start with REG if ratio > 0.5, otherwise CONFIG
                    need_reg = ratio > 0.5
                else:
                    ideal_regs = total_injections * ratio
                    need_reg = reg_count < ideal_regs
            
            # Get scheduled module
            scheduled_module = module_selector.get_next_module_scheduled()
            
            # Try to pick from scheduled module while respecting ratio
            target = self._try_pick_from_module(
                module_name=scheduled_module,
                module_library=module_library,
                need_reg=need_reg,
                repeat=repeat
            )
            
            if target is not None:
                # Success: add to pool and record
                pool.add(target)
                module_selector.record_selection(scheduled_module)
                
                if target.kind == TargetKind.REG:
                    reg_count += 1
                else:
                    config_count += 1
                continue
            
            # Scheduled module couldn't provide needed target kind
            # Try other modules to respect ratio (rebalancing)
            found = False
            for other_module in selected_modules:
                if other_module == scheduled_module:
                    continue
                
                target = self._try_pick_from_module(
                    module_name=other_module,
                    module_library=module_library,
                    need_reg=need_reg,
                    repeat=repeat
                )
                
                if target is not None:
                    pool.add(target)
                    module_selector.record_selection(other_module)
                    
                    if target.kind == TargetKind.REG:
                        reg_count += 1
                    else:
                        config_count += 1
                    
                    found = True
                    break
            
            if found:
                continue

            
            # Cannot respect ratio anymore
            if ratio_strict:
                # Strict mode: stop when ratio cannot be maintained
                break
            
            # Pick any available target (fallback mode)
            # Start with most underselected module to maintain balance
            available_modules = [
                m for m in selected_modules
                if self._has_any_targets(module_library[m], repeat)
            ]
            

            if not available_modules:
                # All modules exhausted
                break
            
            rebalance_module = module_selector.get_most_underselected(available_modules)
            target = self._pick_any_from_module(
                module_name=rebalance_module,
                module_library=module_library,
                repeat=repeat
            )


            if target is not None:
                pool.add(target)
                module_selector.record_selection(rebalance_module)
                
                if target.kind == TargetKind.REG:
                    reg_count += 1
                else:
                    config_count += 1
            else:
                # Should not happen, but break if it does
                break
        
        return pool

    def _try_pick_from_module(
        self,
        module_name: str,
        module_library: Dict,
        need_reg: bool,
        repeat: bool
    ) -> Optional[TargetSpec]:
        """
        Try to pick a target of specified kind from module.
        
        Args:
            module_name: Module to pick from
            module_library: Library with all targets
            need_reg: True if REG needed, False if CONFIG needed
            repeat: Allow cycling
        
        Returns:
            TargetSpec or None if unavailable
        """
        lib = module_library[module_name]
        
        if need_reg:
            targets = lib["reg"]
            idx_key = "reg_idx"
        else:
            targets = lib["config"]
            idx_key = "config_idx"
        
        if lib[idx_key] < len(targets):
            target = targets[lib[idx_key]]
            lib[idx_key] += 1
            
            # Handle repeat cycling
            if repeat and lib[idx_key] >= len(targets):
                lib[idx_key] = 0
            
            return target
        elif repeat and len(targets) > 0:
            # Cycle back
            lib[idx_key] = 0
            target = targets[0]
            lib[idx_key] = 1
            return target
        else:
            return None

    def _pick_any_from_module(
        self,
        module_name: str,
        module_library: Dict,
        repeat: bool
    ) -> Optional[TargetSpec]:
        """
        Pick any available target from module (CONFIG or REG).
        
        Args:
            module_name: Module to pick from
            module_library: Library with all targets
            repeat: Allow cycling
        
        Returns:
            TargetSpec or None if module exhausted
        """
        lib = module_library[module_name]
        
        # Try CONFIG first
        if lib["config_idx"] < len(lib["config"]):
            target = lib["config"][lib["config_idx"]]
            lib["config_idx"] += 1
            if repeat and lib["config_idx"] >= len(lib["config"]):
                lib["config_idx"] = 0
            return target
        
        # Try REG
        if lib["reg_idx"] < len(lib["reg"]):
            target = lib["reg"][lib["reg_idx"]]
            lib["reg_idx"] += 1
            if repeat and lib["reg_idx"] >= len(lib["reg"]):
                lib["reg_idx"] = 0
            return target
        
        # Try cycling if repeat enabled
        if repeat:
            if len(lib["config"]) > 0:
                lib["config_idx"] = 0
                target = lib["config"][0]
                lib["config_idx"] = 1
                return target
            elif len(lib["reg"]) > 0:
                lib["reg_idx"] = 0
                target = lib["reg"][0]
                lib["reg_idx"] = 1
                return target
        
        return None

    def _has_any_targets(self, lib: Dict, repeat: bool) -> bool:
        """
        Check if module library has any targets available.
        
        Args:
            lib: Module library entry
            repeat: Whether repeat mode is enabled
        
        Returns:
            True if targets available
        """
        if repeat:
            # In repeat mode, any non-empty list means available
            return len(lib["config"]) > 0 or len(lib["reg"]) > 0
        else:
            # In non-repeat mode, check if indices haven't reached end
            return (lib["config_idx"] < len(lib["config"]) or
                    lib["reg_idx"] < len(lib["reg"]))

    def _find_register_name(self, board_dict, reg_id: int) -> str:
        """
        Look up register name from board dictionary.
        
        Args:
            board_dict: BoardDict with register information
            reg_id: Register ID to look up
        
        Returns:
            Register name, or fallback if not found
        """
        if reg_id in board_dict.registers:
            return board_dict.registers[reg_id].name
        return f"reg_{reg_id}"


    def _select_modules(self, board_dict) -> List[str]:
        """
        Select modules based on include/exclude arguments.
        
        Logic:
        1. Parse targets list (empty means all modules)
        2. Parse exclude list
        3. Apply both filters
        4. Validate at least one module remains
        
        Args:
            board_dict: BoardDict with available targets (representing modules)
        
        Returns:
            List of selected module/target names
        
        Raises:
            ValueError: If no modules selected after filtering
        """
        all_modules = list(board_dict.targets.keys())  
        
        # Parse target list (comma-separated, empty means all)
        include_str = self.args.get("targets", "")
        
        if include_str:
            include = [m.strip() for m in include_str.split(",") if m.strip()]
        else:
            include = all_modules  # Empty include means all modules
        
        # Parse exclude list (comma-separated)
        exclude_str = self.args.get("exclude", "")
        if exclude_str:
            exclude = [m.strip() for m in exclude_str.split(",") if m.strip()]
        else:
            exclude = []
        
        # Apply filters
        selected = [m for m in include if m in all_modules and m not in exclude]
        
        if not selected:
            raise ValueError(
                f"No modules selected after filtering. "
                f"Available: {all_modules}, Include: {include}, Exclude: {exclude}"
            )
        
        return selected

    def _find_register_name(self, board_dict, reg_id: int) -> str:
        """
        Look up register name from board dictionary.
        
        Args:
            board_dict: BoardDict with register information
            reg_id: Register ID to look up
        
        Returns:
            Register name, or "unknown" if not found
        """
        # board_dict.registers is now a dict mapping reg_id → RegisterInfo
        if reg_id in board_dict.registers:
            return board_dict.registers[reg_id].name
        return f"reg_{reg_id}"  # Fallback if not found
    