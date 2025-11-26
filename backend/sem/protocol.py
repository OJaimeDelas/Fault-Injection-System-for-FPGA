# =============================================================================
# FATORI-V • Fault Injection Framework
# File: fi/semio/protocol.py
# -----------------------------------------------------------------------------
# SEM monitor protocol helpers on top of the UART transport.
#
# Responsibilities
#   • Synchronize to the SEM prompt (I>/O>/D>).
#   • Execute directed state changes (Idle/Observe) and return the raw echo.
#   • Issue status query ('S') and parse counters into a dictionary.
#   • Send an injection command ('N <LFA>') without implicit state changes.
#
# Design
#   • This layer does not own the UART; it only uses the provided transport.
#   • Prompt detection uses a regex configured by the console settings so the
#     operator can tune it centrally if the monitor banner differs.
#   • No background reads occur here to avoid contention with the transport's
#     single reader thread.
# =============================================================================

from __future__ import annotations

import re
import time
from typing import Dict, List, Optional

from fi.backend.sem.transport import SemTransport
from fi.console import console_settings as cs
from fi.console import console_styling as sty
from fi.core.logging.events import log_sem_command


class SemProtocol:
    """
    Stateless helpers over SemTransport for SEM monitor commands.
    Methods here issue commands and collect/parse the immediate reply window.
    Long-running RX consumption remains in the transport's reader thread.
    """

    def __init__(self, tr: SemTransport) -> None:
        self._tr = tr
        # Compile prompt detector once using the console's pattern.
        self._re_prompt = re.compile(getattr(cs, "PROMPT_REGEX", r"^[IOD]>\s*$"))

    # ------------------------------- primitives --------------------------------
    def sync_prompt(self, *, window_s: float = 0.5) -> None:
        """
        Drain until a prompt-like line is seen. Intended to be called once at
        startup to align with SEM's current state.
        """
        deadline = time.monotonic() + max(0.0, float(window_s))
        collected: List[str] = []
        while time.monotonic() < deadline:
            for ln in self._tr.read_lines(timeout_s=0.05):
                collected.append(ln)
                if self._re_prompt.match(ln):
                    return
        # If no prompt is seen, proceed; the caller may still be able to talk.

    def goto_idle(self) -> List[str]:
        """
        Send 'I' to enter Idle and collect the short echo window.
        Returns the raw lines observed during the transition.
        """
        self._tr.write_line("I")
        lines = self._collect_until_prompt()
        
        # Log SEM interaction
        log_sem_command("I", lines)
        
        return lines

    def goto_observe(self) -> List[str]:
        """
        Send 'O' to enter Observation and collect the short echo window.
        Returns the raw lines observed during the transition.
        """
        self._tr.write_line("O")
        lines = self._collect_until_prompt()
        
        # Log SEM interaction
        log_sem_command("O", lines)
        
        return lines

    def status(self) -> Dict[str, str]:
        """
        Send 'S' and parse basic counters returned by the monitor.
        Parsing is tolerant to banners and echoes; only 'AA VV' pairs are kept.
        """
        self._tr.write_line("S")
        # Collect a short window; status responses are brief.
        lines = self._collect_short_window()
        
        # Log SEM interaction
        log_sem_command("S", lines)
        
        counters: Dict[str, str] = {}
        for ln in lines:
            m = re.match(r"^([A-Z]{2})\s+([0-9A-FXx]+)$", ln.strip())
            if m:
                counters[m.group(1)] = m.group(2)
        return counters

    def inject_lfa(self, lfa_hex: str) -> None:
        """
        Issue an injection command using the LFA encoding. No implicit state
        management occurs here; higher layers own policy decisions.
        """
        command = f"N {lfa_hex}"
        self._tr.write_line(command)
        
        # Collect response (typically "SC 10" then "SC 00" then prompt)
        lines = self._collect_short_window()
        
        # Log SEM interaction
        log_sem_command(command, lines)

    def passthrough(self, raw: str) -> None:
        """Send an arbitrary raw SEM command line."""
        self._tr.write_line(raw)

    # ------------------------------- collection helpers -----------------------
    def _collect_until_prompt(self, *, max_wait_s: float = 0.5) -> List[str]:
        """
        Collect lines until a prompt is seen or the timeout expires. The result
        contains every line observed, including the prompt itself if present.
        """
        deadline = time.monotonic() + max(0.0, float(max_wait_s))
        out: List[str] = []
        while time.monotonic() < deadline:
            lines = self._tr.read_lines(timeout_s=0.05)
            if not lines:
                continue
            out.extend(lines)
            if any(self._re_prompt.match(ln) for ln in lines):
                break
        return out

    def _collect_short_window(self, *, window_s: float = 0.3) -> List[str]:
        """
        Collect a brief, fixed-duration window of lines. Suitable for short,
        self-delimited responses like status reports.
        """
        deadline = time.monotonic() + max(0.0, float(window_s))
        out: List[str] = []
        while time.monotonic() < deadline:
            out.extend(self._tr.read_lines(timeout_s=0.05))
        return out