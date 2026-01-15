# =============================================================================
# FATORI-V • FI Engine
# File: injection_controller.py
# -----------------------------------------------------------------------------
# Simplified injection controller for time profiles.
#=============================================================================

from typing import Optional
import time
import logging

from fi.targets.pool import TargetPool
from fi.targets.types import TargetSpec
from fi.targets import router
from fi.core.logging.events import log_injection

logger = logging.getLogger(__name__)


class InjectionController:
    """
    Controller for time profiles to execute injections.
    
    This controller provides a clean API for time profiles:
    - Iterate through pre-built TargetPool
    - Route targets to SEM or register injection backend
    - Log injection results
    - Track statistics
    - Provide timing utilities
    - Synchronize with external benchmarks (optional)
    
    Responsibilities:
        - Target iteration (pop_next from pool)
        - Injection routing (delegate to router)
        - Statistics tracking (total, successes, failures)
        - Timing helpers (sleep)
        - Stop control (for early termination)
        - Benchmark synchronization (optional file-based)
    
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
        log_ctx,
        benchmark_sync=None
    ):
        """
        Initialize injection controller.
        
        Args:
            sem_proto: SEM protocol wrapper for CONFIG injections
            target_pool: Pre-built TargetPool ready for injection
            board_if: Board interface for REG injections
            log_ctx: Logging context (currently unused, kept for compatibility)
            benchmark_sync: Optional BenchmarkSync for external coordination
        """
        self._sem_proto = sem_proto
        self._pool = target_pool
        self._board_if = board_if
        self._log_ctx = log_ctx
        self._benchmark_sync = benchmark_sync
        
        # Statistics tracking
        self._total_injections = 0
        self._successes = 0
        self._failures = 0
        
        # Stop flag for early termination
        self._stop_flag = False

        # Termination reason tracking
        # Set by time profiles or controller when campaign ends
        self._termination_reason = "unknown"
    
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
        
        Execution priority order:
        1. Check external benchmark sync (if enabled)
        2. Capture timestamp BEFORE injection (accuracy critical)
        3. Route target to backend (SEM or register injection, non-blocking)
        4. Update statistics
        5. Log injection with captured timestamp (async)
        6. Update sync tracking
        
        The timestamp is captured immediately before injection to ensure
        maximum accuracy. This allows time profiles to maintain precise
        injection rates regardless of logging or other overhead.
        
        Args:
            target: TargetSpec to inject
        
        Returns:
            True if injection succeeded, False otherwise
        
        Example:
            >>> target = controller.next_target()
            >>> if target:
            ...     success = controller.inject_target(target)
        """
        # Check if benchmark stopped (periodic file check)
        if self._benchmark_sync and self._benchmark_sync.should_check():
            if not self._benchmark_sync.check_benchmark_active():
                logger.info("Benchmark stopped - halting campaign")
                self.request_stop()
                return False
        
        self._total_injections += 1

        # Capture timestamp BEFORE injection for maximum accuracy
        # This ensures logged times reflect actual injection moments,
        # not completion times or logging times
        injection_timestamp = time.monotonic()
        
        # Route to appropriate backend (CONFIG → SEM, REG → UART register injection)
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
        
        # Log injection result with captured timestamp
        # Logging happens after injection to avoid delaying next injection
        log_injection(target, success, timestamp=injection_timestamp)
        
        # Update sync tracking (increment injection counter)
        if self._benchmark_sync:
            self._benchmark_sync.on_injection()
        
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
            "failures": self._failures,
            "termination_reason": self._termination_reason
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
        or external monitoring (including benchmark sync).
        
        Example:
            >>> # In signal handler
            >>> def handle_sigint(sig, frame):
            ...     controller.request_stop()
        """
        self._stop_flag = True
    
    
    def set_termination_reason(self, reason: str):
        """
        Set the reason why the campaign is terminating.
        
        This should be called by time profiles when they detect a termination
        condition (pool exhausted, duration reached, etc.).
        
        Args:
            reason: Human-readable termination reason
            
        Example reasons:
            - "Target pool exhausted"
            - "Duration limit reached"
            - "Benchmark stopped"
            - "User interrupt"
            - "Stop requested"
        """
        self._termination_reason = reason
    
    def get_termination_reason(self) -> str:
        """
        Get the reason why the campaign terminated.
        
        Returns:
            Termination reason string
        """
        return self._termination_reason


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
    log_ctx,
    benchmark_sync=None
) -> InjectionController:
    """
    Factory function to create InjectionController.
    
    This function provides a clean interface for creating controllers
    without needing to import the class directly.
    
    Args:
        sem_proto: SEM protocol wrapper
        target_pool: Pre-built TargetPool
        board_if: Board interface for UART-based register injection
        log_ctx: Logging context
        benchmark_sync: Optional BenchmarkSync for external coordination
    
    Returns:
        Initialized InjectionController
    
    Example:
        >>> controller = create_injection_controller(
        ...     sem_proto=proto,
        ...     target_pool=pool,
        ...     board_if=board_if,
        ...     log_ctx=log_ctx,
        ...     benchmark_sync=sync
        ... )
    """
    return InjectionController(
        sem_proto=sem_proto,
        target_pool=target_pool,
        board_if=board_if,
        log_ctx=log_ctx,
        benchmark_sync=benchmark_sync
    )