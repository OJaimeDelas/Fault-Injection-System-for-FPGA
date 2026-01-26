# =============================================================================
# FATORI-V • FI Core Campaign Sync
# File: sync.py
# -----------------------------------------------------------------------------
# Benchmark synchronization via file-based signaling.
#=============================================================================

import time
from pathlib import Path
from typing import Optional
import logging
from fi.core.logging.events import (
    log_sync_waiting,
    log_sync_ready,
    log_sync_timeout,
    log_sync_stopped
)

logger = logging.getLogger(__name__)


class BenchmarkSync:
    """
    Manages synchronization with external benchmarks via signal files.
    
    This class provides a simple file-based coordination mechanism that allows
    the FI system to synchronize with external benchmark processes. The benchmark
    creates a signal file when ready, and removes it when done. The FI system
    waits for the file to appear before starting, then periodically checks if
    the file still exists during execution.
    
    Mechanism:
    1. Wait for signal file to appear (blocks campaign start)
    2. Run campaign normally
    3. Periodically check if file still exists
    4. Stop gracefully if file disappears
    
    Checking happens at whichever comes first:
    - Time-based: Every check_interval_s seconds
    - Count-based: Every check_every_n injections
    
    This hybrid approach balances responsiveness (time-based) with efficiency
    (count-based) to minimize file system overhead during high-frequency injection.
    """
    
    def __init__(
        self,
        sync_file_path: Optional[str],
        check_interval_s: float = 1.0,
        check_every_n: int = 100
    ):
        """
        Initialize benchmark synchronization.
        
        Args:
            sync_file_path: Path to signal file (None disables sync)
            check_interval_s: Minimum seconds between file checks
            check_every_n: Minimum injections between file checks
        """
        self.sync_file_path = Path(sync_file_path) if sync_file_path else None
        self.check_interval_s = check_interval_s
        self.check_every_n = check_every_n
        
        # Tracking variables for hybrid checking
        self.last_check_time = 0.0
        self.injection_count = 0
        
        # State tracking
        self.enabled = sync_file_path is not None
        self.file_appeared = False
        self.file_disappeared = False
    
    def wait_for_benchmark_ready(self, timeout_s: Optional[float] = None) -> bool:
        """
        Wait for signal file to appear, then replace contents with "READY".
        
        This function blocks campaign execution until the benchmark signals
        readiness by creating the signal file. Once detected, the file contents
        are replaced with "READY" to signal back to the benchmark.
        
        Args:
            timeout_s: Maximum seconds to wait (None = wait forever)
        
        Returns:
            True if file appeared and replaced, False if timeout occurred
        """
        if not self.enabled:
            # Sync disabled - immediately ready
            return True
        
        log_sync_waiting(str(self.sync_file_path))
        
        start_time = time.time()
        
        while True:
            # Check if signal file exists
            if self.sync_file_path.exists():
                log_sync_ready()
                self.file_appeared = True
                self.last_check_time = time.time()
                
                # Replace file contents with "READY"
                try:
                    with self.sync_file_path.open('w') as f:
                        f.write("READY")
                except Exception as e:
                    # Log but don't fail - sync file detection succeeded
                    from fi.core.logging.events import log_event
                    log_event('WARNING', message=f"Could not replace sync file contents: {e}")
                
                return True
            
            # Check timeout if specified
            if timeout_s and (time.time() - start_time) > timeout_s:
                log_sync_timeout(timeout_s)
                return False
            
            # Sleep briefly to avoid spinning CPU
            time.sleep(0.1)
    
    def should_check(self) -> bool:
        """
        Determine if it's time to verify file still exists.
        
        Uses hybrid checking logic: returns True when EITHER time interval
        OR injection count threshold is reached. This ensures timely response
        to benchmark termination while minimizing file system overhead.
        
        Returns:
            True if check should be performed, False otherwise
        """
        if not self.enabled or not self.file_appeared:
            # Sync disabled or not started yet
            return False
        
        # Check time-based condition
        time_elapsed = time.time() - self.last_check_time
        if time_elapsed >= self.check_interval_s:
            return True
        
        # Check count-based condition
        if self.injection_count >= self.check_every_n:
            return True
        
        return False
    
    def check_benchmark_active(self) -> bool:
        """
        Check if benchmark signal file still exists.
        
        Called when should_check() returns True. Verifies the signal file
        is still present, indicating the benchmark is still running.
        
        Returns:
            True if benchmark still active, False if stopped
        """
        if not self.enabled:
            # Sync disabled - always active
            return True
        
        # Check file existence
        exists = self.sync_file_path.exists()
        
        if not exists:
            log_sync_stopped()
            self.file_disappeared = True
        
        # Reset tracking counters after check
        self.last_check_time = time.time()
        self.injection_count = 0
        
        return exists
    
    def on_injection(self):
        """
        Update injection counter for count-based checking.
        
        Called after each injection to track how many have occurred since
        the last file check. Used in hybrid checking logic.
        """
        if self.enabled:
            self.injection_count += 1