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
    
    CRITICAL TIMING REQUIREMENT:
    The inject_register() method MUST return immediately without
    waiting for hardware acknowledgment. Time profiles depend on
    precise injection timing, and any blocking wait will compromise
    campaign timing accuracy.
    
    Correct: Send command → return immediately
    Wrong: Send command → wait for ack → return
    """
    
    @abstractmethod
    def inject_register(self, reg_id: int, bit_index: int = None) -> bool:
        """
        Inject fault into register.
        
        MUST BE NON-BLOCKING: This method must send the injection
        command and return immediately. Do not wait for hardware
        acknowledgment or verification.
        
        Args:
            reg_id: Register ID to inject into
            bit_index: Optional bit index within register (for bit-level injection)
        
        Returns:
            True if injection command sent successfully, False otherwise
            (Note: True means command sent, not that fault occurred)
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
        
        Returns immediately (non-blocking as required).
        
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
    
    IMPLEMENTATION NOTE:
    This class uses fire-and-forget transmission. The inject_register()
    method sends the register ID via GPIO and returns immediately without
    waiting for FPGA acknowledgment. This is required for maintaining
    precise injection timing in campaigns.
    """
    
    def __init__(self, config, transport=None):
        """
        Initialize GPIO board interface.
        
        Args:
            config: Config object with GPIO settings
            transport: SemTransport instance for UART communication (optional)
        """
        self.transport = transport
        self.idle_id = config.gpio_idle_id
        self.reg_id_width = config.gpio_reg_id_width
        
        # Calculate max register ID based on bit width
        self.max_reg_id = (1 << self.reg_id_width) - 1
        
        from fi.core.logging.events import log_gpio_init
        # Log "UART" as interface type instead of pin number
        log_gpio_init("UART", self.idle_id, self.reg_id_width, self.max_reg_id)
    


    def inject_register(self, reg_id: int, bit_index: int = None) -> bool:
        """
        Transmit register ID via UART transport.
        
        Sends a 2-byte command to the FPGA UART decoder:
            Byte 0: ASCII 'R' (0x52) - command identifier
            Byte 1: Register ID (1-255) - target register
        
        The FPGA decoder converts this to an fi_port broadcast signal
        that triggers injection in the corresponding CPU register.
        
        FIRE-AND-FORGET: This method sends the command and returns immediately.
        No acknowledgment is waited for. This non-blocking behavior is critical
        for campaign timing accuracy.
        
        Args:
            reg_id: Register ID to inject (1 to max_reg_id)
            bit_index: Optional bit index (currently unused)
        
        Returns:
            True if injection command sent successfully, False if validation failed
            (Note: True means command sent, not that FPGA acknowledged)
        """
        from fi.core.logging.events import log_gpio_inject
        log_gpio_inject(reg_id, bit_index)
        
        # Validate register ID
        if reg_id < 1 or reg_id > self.max_reg_id:
            from fi.core.logging.events import log_gpio_error
            log_gpio_error(reg_id, self.reg_id_width, self.max_reg_id)
            return False
        
        # If no transport available, log placeholder and return
        if self.transport is None:
            from fi.core.logging.events import log_gpio_placeholder
            log_gpio_placeholder()
            return True
        
        # Send 2-byte command: 'R' (0x52) followed by register ID byte
        command = bytes([0x52, reg_id])
        self.transport.write_bytes(command)
        
        return True


def create_board_interface(cfg, transport=None):
    """
    Factory function to create appropriate board interface.
    
    Creates either a real GPIO interface or a NoOp stub based on
    the cfg.gpio_force_disabled flag.
    
    Args:
        cfg: Config object with GPIO settings
        transport: Optional SemTransport instance for UART-based injection
    
    Returns:
        BoardInterface instance (either GPIOBoardInterface or NoOpBoardInterface)
    
    Example:
        >>> transport, sem_proto = open_sem(cfg, log_ctx)
        >>> board_if = create_board_interface(cfg, transport=transport)
        >>> board_if.inject_register(reg_id=99)
    """
    # This factory is only called when GPIO is explicitly needed
    # The conditional logic is in fault_injection.py
    # This just handles the force_disabled flag
    if cfg.gpio_force_disabled:
        logger.info("Creating NoOp board interface (force disabled)")
        return NoOpBoardInterface()
    else:
        logger.info("Creating GPIO board interface (UART-based)")
        return GPIOBoardInterface(cfg, transport=transport)