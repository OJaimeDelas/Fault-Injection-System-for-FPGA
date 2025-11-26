# =============================================================================
# FATORI-V • FI Engine
# File: injection_controller.py
# -----------------------------------------------------------------------------
# Simplified injection controller for time profiles.
#=============================================================================

from typing import Optional
import time

from fi.targets.pool import TargetPool
from fi.targets.types import TargetSpec
from fi.targets import router
from fi.core.logging.events import log_injection


class InjectionController:
    """
    Controller for time profiles to execute injections.
    
    This controller provides a clean API for time profiles:
    - Iterate through pre-built TargetPool
    - Route targets to SEM or GPIO backend
    - Log injection results
    - Track statistics
    - Provide timing utilities
    
    Responsibilities:
        - Target iteration (pop_next from pool)
        - Injection routing (delegate to router)
        - Statistics tracking (total, successes, failures)
        - Timing helpers (sleep)
        - Stop control (for early termination)
    
    NOT responsible for:
        - Building TargetPool (done by area profiles)
        - Loading SystemDict (done before controller creation)
        - ACME operations (done during pool building)
        - Configuration management (handled by Config)
    
    The controller is deliberately simple and focused. All complexity
    has been pushed to earlier stages (pool building) or backend
    modules (router, SEM protocol, board interface).
    """
    
    def __init__(
        self,
        sem_proto,
        target_pool: TargetPool,
        board_if,
        log_ctx
    ):
        """
        Initialize injection controller.
        
        Args:
            sem_proto: SEM protocol wrapper for CONFIG injections
            target_pool: Pre-built TargetPool ready for injection
            board_if: Board interface for REG injections
            log_ctx: Logging context (currently unused, kept for compatibility)
        """
        self._sem_proto = sem_proto
        self._pool = target_pool
        self._board_if = board_if
        self._log_ctx = log_ctx
        
        # Statistics tracking
        self._total_injections = 0
        self._successes = 0
        self._failures = 0
        
        # Stop flag for early termination
        self._stop_flag = False
    
    # -------------------------------------------------------------------------
    # Target iteration
    # -------------------------------------------------------------------------
    
    def next_target(self) -> Optional[TargetSpec]:
        """
        Get next target from pool.
        
        Returns the next TargetSpec in injection order, or None when
        the pool is exhausted.
        
        Returns:
            Next TargetSpec, or None if pool exhausted
        
        Example:
            >>> while (target := controller.next_target()) is not None:
            ...     controller.inject_target(target)
        """
        return self._pool.pop_next()
    
    # -------------------------------------------------------------------------
    # Injection
    # -------------------------------------------------------------------------
    
    def inject_target(self, target: TargetSpec) -> bool:
        """
        Route target to appropriate backend and log result.
        
        This method:
        1. Routes target to SEM (CONFIG) or GPIO (REG) via router
        2. Updates statistics
        3. Logs injection result
        
        Args:
            target: TargetSpec to inject
        
        Returns:
            True if injection succeeded, False otherwise
        
        Example:
            >>> target = controller.next_target()
            >>> if target:
            ...     success = controller.inject_target(target)
        """
        self._total_injections += 1
        
        # Route to appropriate backend (CONFIG → SEM, REG → GPIO)
        # Note: router.inject_target handles the dispatching
        success = router.inject_target(
            target=target,
            sem_proto=self._sem_proto,
            board_if=self._board_if,
            logger=None  # We handle logging ourselves
        )
        
        # Update statistics
        if success:
            self._successes += 1
        else:
            self._failures += 1
        
        # Log injection result
        log_injection(target, success)
        
        return success
    
    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> dict:
        """
        Get injection statistics.
        
        Returns dictionary with:
        - total: Total injections attempted
        - successes: Number of successful injections
        - failures: Number of failed injections
        
        Returns:
            Dict with injection statistics
        
        Example:
            >>> stats = controller.get_stats()
            >>> print(f"{stats['successes']}/{stats['total']} succeeded")
        """
        return {
            "total": self._total_injections,
            "successes": self._successes,
            "failures": self._failures
        }
    
    # -------------------------------------------------------------------------
    # Stop control
    # -------------------------------------------------------------------------
    
    def should_stop(self) -> bool:
        """
        Check if campaign should stop.
        
        Time profiles that support early termination should check this
        flag in their main loop and exit gracefully when True.
        
        Returns:
            True if stop has been requested
        
        Example:
            >>> while not controller.should_stop():
            ...     target = controller.next_target()
            ...     if target:
            ...         controller.inject_target(target)
        """
        return self._stop_flag
    
    def request_stop(self):
        """
        Request campaign to stop.
        
        Sets the stop flag. Time profiles should check should_stop()
        and exit gracefully. This is typically called by signal handlers
        or external monitoring.
        
        Example:
            >>> # In signal handler
            >>> def handle_sigint(sig, frame):
            ...     controller.request_stop()
        """
        self._stop_flag = True
    
    # -------------------------------------------------------------------------
    # Timing utilities
    # -------------------------------------------------------------------------
    
    def sleep(self, seconds: float):
        """
        Sleep for given duration.
        
        Time profiles use this instead of time.sleep() directly so that
        timing behavior is centralized and can be mocked for testing.
        
        Args:
            seconds: Duration to sleep in seconds
        
        Example:
            >>> # Inject with 1 second delay between injections
            >>> target = controller.next_target()
            >>> controller.inject_target(target)
            >>> controller.sleep(1.0)
        """
        if seconds > 0:
            time.sleep(seconds)


# -----------------------------------------------------------------------------
# Factory function
# -----------------------------------------------------------------------------

def create_injection_controller(
    sem_proto,
    target_pool: TargetPool,
    board_if,
    log_ctx
) -> InjectionController:
    """
    Factory function to create InjectionController.
    
    This function provides a clean interface for creating controllers
    without needing to import the class directly.
    
    Args:
        sem_proto: SEM protocol wrapper
        target_pool: Pre-built TargetPool
        board_if: Board interface for GPIO
        log_ctx: Logging context
    
    Returns:
        Initialized InjectionController
    
    Example:
        >>> controller = create_injection_controller(
        ...     sem_proto=proto,
        ...     target_pool=pool,
        ...     board_if=board_if,
        ...     log_ctx=log_ctx
        ... )
    """
    return InjectionController(
        sem_proto=sem_proto,
        target_pool=target_pool,
        board_if=board_if,
        log_ctx=log_ctx
    )