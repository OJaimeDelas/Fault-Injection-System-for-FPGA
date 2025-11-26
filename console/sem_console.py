# =============================================================================
# FATORI-V • FI SEM Console
# File: sem_console.py
# -----------------------------------------------------------------------------
# Interactive console for the SEM IP. Provides a simple REPL to issue status,
# mode-change, and injection commands over UART.
#=============================================================================

from __future__ import annotations

import argparse
import sys
from typing import Optional

from fi import fi_settings as settings
from fi.backend.sem.transport import SemTransport
from fi.backend.sem.protocol import SemProtocol
from fi.console import console_settings as cs
from fi.console import console_styling as sty


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """
    Build and parse the argument list for the SEM console.

    Only serial parameters are exposed here. Higher-level campaigns use the
    FI engine; this console is aimed at manual inspection and debugging.
    """
    parser = argparse.ArgumentParser(
        prog="fi.console.sem_console",
        description="Interactive SEM console over UART.",
    )

    parser.add_argument(
        "--dev",
        default=settings.DEFAULT_SEM_DEVICE,
        help="Serial device path for SEM UART (e.g. /dev/ttyUSB0).",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=settings.DEFAULT_SEM_BAUDRATE,
        help="Serial baudrate for SEM UART.",
    )

    return parser.parse_args(argv)


def _open_sem(device: str, baudrate: int) -> tuple[SemTransport, SemProtocol]:
    """
    Open the semantics of the SEM link: transport and protocol.

    The transport handles raw UART I/O. The protocol wraps this in a
    higher-level command set that knows how to speak to the SEM IP.
    """
    transport = SemTransport(device=device, baudrate=baudrate)
    proto = SemProtocol(transport=transport, sem_clock_hz=settings.SEM_CLOCK_HZ)
    proto.sync_prompt()
    return transport, proto


def _print_banner(device: str, baudrate: int) -> None:
    """
    Print a small banner with connection information and optional hints.

    The behaviour is controlled by console_settings flags so it can be tuned
    without modifying the console logic.
    """
    title = sty.style_title("FATORI-V • SEM Console")
    print(title)
    print(f"  Device : {device}")
    print(f"  Baud   : {baudrate}")
    print()

    if cs.SHOW_START_MODE:
        # At startup the console does not know the actual SEM mode; that
        # information is obtained via a status query. This hint simply
        # reminds the user what to expect.
        print(sty.style_hint("Hint: use 'status' to query the current SEM mode."))
        print()

    if cs.SHOW_CONSOLE_COMMANDS:
        print(sty.style_hint("Commands:"))
        print("  status            - query SEM status")
        print("  idle              - switch SEM to Idle mode")
        print("  observe           - switch SEM to Observe mode")
        print("  inject <LFA_HEX>  - inject a configuration address")
        print("  help              - show this help")
        print("  exit / quit       - leave the console")
        print()

    if cs.SHOW_SEM_CHEATSHEET:
        print(sty.style_hint("SEM cheatsheet (short):"))
        print("  Idle    - SEM ready but not observing configuration RAM")
        print("  Observe - SEM scanning configuration frames for errors")
        print("  Inject  - SEM performs a single-bit flip at given LFA")
        print()


def _handle_command(proto: SemProtocol, line: str) -> bool:
    """
    Handle a single command line.

    Returns True to keep the REPL running, or False to request exit.
    """
    stripped = line.strip()
    if not stripped:
        return True

    parts = stripped.split()
    cmd = parts[0].lower()
    args = parts[1:]

    try:
        if cmd in ("exit", "quit"):
            return False

        if cmd == "help":
            # Reuse the banner help section for simplicity.
            print(sty.style_hint("Commands:"))
            print("  status            - query SEM status")
            print("  idle              - switch SEM to Idle mode")
            print("  observe           - switch SEM to Observe mode")
            print("  inject <LFA_HEX>  - inject a configuration address")
            print("  help              - show this help")
            print("  exit / quit       - leave the console")
            return True

        if cmd == "status":
            status_info = proto.status()
            if isinstance(status_info, str):
                print(status_info)
            elif status_info is not None:
                print(repr(status_info))
            return True

        if cmd == "idle":
            proto.goto_idle()
            return True

        if cmd == "observe":
            proto.goto_observe()
            return True

        if cmd == "inject":
            if not args:
                print(sty.style_error("inject requires an LFA argument."), file=sys.stderr)
                return True

            lfa = args[0].strip().lower()
            if lfa.startswith("0x"):
                lfa = lfa[2:]
            lfa = lfa.upper()

            if not lfa:
                print(sty.style_error("Empty LFA string."), file=sys.stderr)
                return True

            proto.inject_lfa(lfa)
            return True

        print(sty.style_error(f"Unknown command: {cmd!r}"), file=sys.stderr)
        return True

    except KeyboardInterrupt:
        # Allow Ctrl+C to interrupt a long-running command without leaving
        # the console entirely.
        print(sty.style_error("Command interrupted."), file=sys.stderr)
        return True

    except Exception as exc:  # noqa: BLE001
        print(sty.style_error(f"Error while executing command: {exc!r}"), file=sys.stderr)
        return True


def main(argv: Optional[list[str]] = None) -> int:
    """
    Entry point for the interactive SEM console.

    The function sets up the link to SEM, prints a banner, then runs a REPL
    that accepts simple textual commands until the user exits.
    """
    args = _parse_args(argv)

    transport: SemTransport | None = None
    proto: SemProtocol | None = None

    try:
        transport, proto = _open_sem(args.dev, args.baud)

        _print_banner(args.dev, args.baud)

        # Main REPL loop. The prompt string is styled by console_settings.
        while True:
            try:
                line = input(sty.style_prompt(cs.PROMPT))
            except EOFError:
                # End-of-file (Ctrl+D) is treated as a request to exit.
                print()
                break

            if not _handle_command(proto, line):
                break

        return 0

    except KeyboardInterrupt:
        # Allow abrupt termination via Ctrl+C during setup or REPL.
        print(sty.style_error("\nSEM console interrupted."), file=sys.stderr)
        return 130

    except Exception as exc:  # noqa: BLE001
        print(sty.style_error(f"[sem_console] Error: {exc!r}"), file=sys.stderr)
        return 1

    finally:
        if transport is not None:
            try:
                transport.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
