# =============================================================================
# FATORI-V • FI Targets
# File: router.py
# -----------------------------------------------------------------------------
# Route targets to appropriate injection backend (SEM or UART register injection).
#=============================================================================

import logging
from fi.targets.types import TargetSpec, TargetKind

logger = logging.getLogger(__name__)


def inject_target(target: TargetSpec, sem_proto, board_if, logger=None) -> bool:
    """
    Inject target by routing to appropriate backend.
    
    This is the main dispatch function that routes targets based on their kind:
    - CONFIG targets → SEM protocol (configuration bits)
    - REG targets → Board interface (registers via UART fi_coms protocol)
    
    Args:
        target: TargetSpec to inject
        sem_proto: SEM protocol wrapper for CONFIG injection
        board_if: Board interface for REG injection
        logger: Optional logger (for compatibility, not used)
    
    Returns:
        True if injection succeeded, False otherwise
    """
    if target.kind == TargetKind.CONFIG:
        return _inject_config_bit(target, sem_proto)
    elif target.kind == TargetKind.REG:
        return _inject_register(target, board_if)
    else:
        logger.error(f"Unknown target kind: {target.kind}")
        return False


def _inject_config_bit(target: TargetSpec, sem_proto) -> bool:
    """
    Inject configuration bit via SEM protocol.
    
    Extracts the configuration address from the target and sends
    it to the SEM IP core via the SEM protocol wrapper. The SEM
    protocol uses the inject_lfa method which sends the 'N <address>'
    command to the SEM monitor.
    
    Args:
        target: TargetSpec with CONFIG kind
        sem_proto: SEM protocol wrapper
    
    Returns:
        True if SEM injection succeeded (always returns True as inject_lfa
        does not return a status, exceptions indicate failure)
    """
    try:
        address = target.config_address
        
        # Send inject command to SEM IP core using LFA encoding
        # The inject_lfa method sends 'N <address>' to SEM monitor
        sem_proto.inject_lfa(address)
        
        # SEM protocol inject_lfa does not return status
        # Assume success unless exception is raised
        return True
    except Exception as e:
        logger.error(f"SEM injection failed for address {target.config_address}: {e}")
        return False


def _inject_register(target: TargetSpec, board_if) -> bool:
    """
    Inject register via board interface (UART).
    
    Extracts the register ID from the target and sends it to the
    board interface, which handles the UART fi_coms command to
    the FPGA injection logic.
    
    Args:
        target: TargetSpec with REG kind
        board_if: Board interface for UART-based register injection
    
    Returns:
        True if register injection succeeded
    """
    try:
        reg_id = target.reg_id
        
        # Send to board interface (UART fi_coms command)
        # The board interface returns True/False for success
        success = board_if.inject_register(reg_id, bit_index=None)
        
        return success
    except Exception as e:
        logger.error(f"Register injection failed for reg_id {target.reg_id}: {e}")
        return False