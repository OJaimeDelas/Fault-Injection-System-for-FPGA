# =============================================================================
# FATORI-V • FI Register Injection
# File: board_interface.py
# -----------------------------------------------------------------------------
# Board interface abstraction for UART-based register fault injection.
#=============================================================================

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BoardInterface(ABC):
    """
    Abstract base class for board-level register injection.
    
    Implementations of this interface provide register-level fault injection
    via different communication methods (UART commands, SPI, I2C, etc.).
    
    The current implementation uses UART-based commands sent through fi_coms
    hardware module, which intercepts 'R' commands and broadcasts register IDs
    to the FPGA injection logic.
    
    CRITICAL TIMING REQUIREMENT:
    The inject_register() method MUST return immediately without
    waiting for hardware acknowledgment. Time profiles depend on
    precise injection timing, and any blocking wait will compromise
    campaign timing accuracy.
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
    Stub implementation that logs but doesn't perform actual register injection.
    
    This is the default implementation used when register injection is disabled.
    It logs all injection requests but doesn't interact with actual hardware.
    
    Use Cases:
        - Testing without hardware
        - Dry-run mode
        - Development without UART connection
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

class UARTBoardInterface(BoardInterface):
    """
    UART-based board interface for register injection via fi_coms protocol.
    
    Sends 2-byte commands ('R' + reg_id) over shared UART connection. The
    fi_coms hardware module intercepts 'R' commands and broadcasts register
    IDs to FPGA injection logic via fi_port signal.
    
    IMPLEMENTATION NOTE:
    This class uses fire-and-forget transmission. The inject_register()
    method sends the register ID via UART and returns immediately without
    waiting for FPGA acknowledgment. This is required for maintaining
    precise injection timing in campaigns.
    """
    
    def __init__(self, config, transport=None):
        """
        Initialize UART board interface for register injection.
        
        Args:
            config: Config object with register injection settings
            transport: SemTransport instance for UART communication (optional)
        """
        self.transport = transport
        self.idle_id = config.reg_inject_idle_id
        self.reg_id_width = config.reg_inject_reg_id_width
        
        # Calculate max register ID based on bit width
        self.max_reg_id = (1 << self.reg_id_width) - 1
        
        from fi.core.logging.events import log_reg_inject_init
        # Log interface type and parameters
        log_reg_inject_init("UART", self.idle_id, self.reg_id_width, self.max_reg_id)
    


    def inject_register(self, reg_id: int, bit_index: int = None) -> bool:
        """
        Transmit register ID via UART transport using fi_coms protocol.
        
        Sends a 2-byte command to the fi_coms hardware module:
            Byte 0: ASCII 'R' (0x52) - command identifier
            Byte 1: Register ID (1-255) - target register
        
        The fi_coms module intercepts this command and broadcasts the register
        ID on fi_port[7:0] signal, triggering injection in the CPU register.
        
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
        from fi.core.logging.events import log_reg_inject_inject
        log_reg_inject_inject(reg_id, bit_index)
        
        # Validate register ID
        if reg_id < 1 or reg_id > self.max_reg_id:
            from fi.core.logging.events import log_reg_inject_error
            log_reg_inject_error(reg_id, self.reg_id_width, self.max_reg_id)
            return False
        
        # If no transport available, log placeholder and return
        if self.transport is None:
            from fi.core.logging.events import log_reg_inject_placeholder
            log_reg_inject_placeholder()
            return True
        
        # Send 2-byte fi_coms command: 'R' (0x52) followed by register ID byte
        command = bytes([0x52, reg_id])
        self.transport.write_bytes(command)
        
        return True


def create_board_interface(cfg, transport=None):
    """
    Factory function to create appropriate board interface.
    
    Creates either a real UART register injection interface or a NoOp stub
    based on the cfg.reg_inject_force_disabled flag.
    
    Args:
        cfg: Config object with register injection settings
        transport: Optional SemTransport instance for UART-based injection
    
    Returns:
        BoardInterface instance (either UARTBoardInterface or NoOpBoardInterface)
    
    Example:
        >>> transport, sem_proto = open_sem(cfg, log_ctx)
        >>> board_if = create_board_interface(cfg, transport=transport)
        >>> board_if.inject_register(reg_id=99)
    """
    # This factory is only called when register injection is explicitly needed
    # The conditional logic is in fault_injection.py
    # This just handles the force_disabled flag
    if cfg.reg_inject_force_disabled:
        logger.info("Creating NoOp board interface (register injection disabled)")
        return NoOpBoardInterface()
    else:
        logger.info("Creating UART board interface for register injection")
        return UARTBoardInterface(cfg, transport=transport)