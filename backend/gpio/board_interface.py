# =============================================================================
# FATORI-V • FI Targets
# File: board_interface.py
# -----------------------------------------------------------------------------
# Board interface abstraction for register-level fault injection.
#=============================================================================

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BoardInterface(ABC):
    """
    Abstract base class for board-level register injection.
    
    Different platforms (Raspberry Pi GPIO, custom FPGA interface,
    SPI/I2C protocol, etc.) implement this interface to provide
    register-level fault injection.
    """
    
    @abstractmethod
    def inject_register(self, reg_id: int, bit_index: int = None) -> bool:
        """
        Inject fault into register.
        
        Args:
            reg_id: Register ID to inject into
            bit_index: Optional bit index within register (for bit-level injection)
        
        Returns:
            True if injection succeeded, False otherwise
        """
        pass


class NoOpBoardInterface(BoardInterface):
    """
    Stub implementation that logs but doesn't perform actual GPIO operations.
    
    This is the default implementation used when GPIO is disabled. It logs
    all injection requests but doesn't interact with actual hardware.
    
    Use Cases:
        - Testing without hardware
        - Dry-run mode
        - Development on systems without GPIO
    """
    
    def inject_register(self, reg_id: int, bit_index: int = None) -> bool:
        """
        Log injection request but don't perform actual injection.
        
        Args:
            reg_id: Register ID
            bit_index: Optional bit index
        
        Returns:
            Always True (simulation mode)
        """
        if bit_index is None:
            logger.info(f"[NoOp] Would inject reg_id={reg_id}")
        else:
            logger.info(f"[NoOp] Would inject reg_id={reg_id}, bit={bit_index}")
        return True

class GPIOBoardInterface(BoardInterface):
    """
    GPIO-based board interface for register injection via serial transmission.
    
    Transmits register IDs serially over a single GPIO pin. The FPGA samples
    the pin to detect register ID changes. When idle, transmits IDLE_ID (0).
    """
    
    def __init__(self, config):
        """
        Initialize GPIO board interface.
        
        Args:
            config: Config object with GPIO settings
        """
        self.gpio_pin = config.gpio_pin
        self.idle_id = config.gpio_idle_id
        self.reg_id_width = config.gpio_reg_id_width
        
        # Calculate max register ID based on bit width
        self.max_reg_id = (1 << self.reg_id_width) - 1
        
        print(
            f"[GPIO] Initialized: pin={self.gpio_pin}, "
            f"idle_id={self.idle_id}, width={self.reg_id_width} bits "
            f"(supports reg_id 1-{self.max_reg_id})"
        )
        
        # TODO: Initialize GPIO hardware for serial transmission
        # Platform-specific implementation needed
    
    def inject_register(self, reg_id: int, bit_index: int = None) -> bool:
        """
        Transmit register ID via GPIO serial pin.
        
        The ID is transmitted serially over the configured GPIO pin.
        The FPGA samples the pin to detect ID changes.
        
        Args:
            reg_id: Register ID to inject (1 to max_reg_id)
            bit_index: Optional bit index (currently unused)
        
        Returns:
            True if injection succeeded
        """
        if bit_index is None:
            print(f"[GPIO] Injecting reg_id={reg_id}")
        else:
            print(f"[GPIO] Injecting reg_id={reg_id}, bit={bit_index}")
        
        # Validate register ID
        if reg_id < 1 or reg_id > self.max_reg_id:
            print(
                f"[GPIO] ERROR: reg_id={reg_id} out of range (1-{self.max_reg_id} "
                f"for {self.reg_id_width}-bit width)"
            )
            return False
        
        # TODO: Implement serial transmission
        # Pseudocode:
        # 1. Set GPIO pin to transmit register ID serially
        # 2. FPGA samples pin to detect ID
        # 3. Wait for acknowledgment (platform-specific)
        
        print("[GPIO] Serial transmission not implemented - returning success (placeholder)")
        return True


def create_board_interface(cfg):
    """
    Factory function to create appropriate board interface.
    
    Creates either a real GPIO interface or a NoOp stub based on
    the cfg.gpio_enabled flag.
    
    Args:
        cfg: Config object with GPIO settings
    
    Returns:
        BoardInterface instance (either GPIOBoardInterface or NoOpBoardInterface)
    
    Example:
        >>> board_if = create_board_interface(cfg)
        >>> board_if.inject_register(reg_id=5)
    """
    if cfg.gpio_enabled:
        logger.info("Creating GPIO board interface (real GPIO control)")
        return GPIOBoardInterface(cfg)
    else:
        logger.info("Creating NoOp board interface (simulation mode)")
        return NoOpBoardInterface()