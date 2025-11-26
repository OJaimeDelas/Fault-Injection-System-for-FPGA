# =============================================================================
# FATORI-V • FI Targets — GPIO Register Decoder
# File: gpio_reg_decoder.py
# -----------------------------------------------------------------------------
# Helpers for handling register-based fault-injection targets.
#
# The FI engine represents all targets as TargetSpec objects. This module
# focuses on targets whose kind is "reg_id" or "reg_bit" and forwards them
# to a board interface that knows how to drive the actual hardware.
#
# The board interface type is defined in fi.targets.board_interface and
# is intentionally minimal: a single inject_register(...) method.
#=============================================================================

from __future__ import annotations

from typing import Any, Optional

from fi.targets.types import TargetSpec
from fi.backend.gpio.board_interface import BoardInterface


def _log(logger: Any, level: str, message: str) -> None:
    """
    Send a message to a logger object if it exposes a matching method.

    The logger is expected to behave like logging.Logger. Any missing
    method or exception during logging is silently ignored so that
    logging never interferes with fault injection.
    """
    if logger is None:
        return
    method = getattr(logger, level, None)
    if not callable(method):
        return
    try:
        method(message)
    except Exception:
        # Logging failures are not considered fatal.
        pass


def inject_register_target(
    target: TargetSpec,
    board_if: BoardInterface,
    logger: Optional[Any] = None,
) -> bool:
    """
    Inject a register-based TargetSpec through the provided board interface.

    target:
        TargetSpec whose kind is "reg_id" or "reg_bit". The reg_id and
        optional bit_index fields are used to steer the injection.
    board_if:
        Instance implementing the BoardInterface protocol.
    logger:
        Optional logger used for informational and error messages.

    Returns:
        True on success, False on failure. Failures include missing fields,
        unsupported kinds, exceptions in the board interface, or an explicit
        False returned by the board implementation.
    """
    # Only register-oriented kinds are accepted here.
    if target.kind not in ("reg_id", "reg_bit"):
        _log(
            logger,
            "error",
            f"gpio_reg_decoder called with non-register target kind '{target.kind}'.",
        )
        return False

    reg_id = target.reg_id
    bit_index = target.bit_index

    if reg_id is None:
        _log(logger, "error", "Register target has no reg_id field set.")
        return False

    # Build a compact description used in logs.
    if bit_index is None:
        desc = f"reg_id={reg_id}"
    else:
        desc = f"reg_id={reg_id}, bit={bit_index}"

    _log(logger, "info", f"Injecting register target ({desc}).")

    try:
        result = board_if.inject_register(reg_id, bit_index)
    except Exception as exc:
        _log(
            logger,
            "error",
            f"BoardInterface.inject_register failed for ({desc}): {exc!r}",
        )
        return False

    # If the board implementation does not return anything, treat that
    # as success. Boolean results are respected; other truthy values are
    # interpreted in the usual Python way.
    if result is None:
        return True
    if isinstance(result, bool):
        return result
    return bool(result)
