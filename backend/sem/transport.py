# =============================================================================
# FATORI-V • Fault Injection Framework
# File: fi/semio/transport.py
# -----------------------------------------------------------------------------
# UART transport wrapper around pyserial with background line framing.
#
# Responsibilities
#   • Open/close the serial link to the SEM monitor.
#   • Perform newline-terminated writes with the configured terminator.
#   • Run a single background reader that accumulates bytes, frames CR/LF
#     terminated lines, and enqueues them for non-blocking consumption.
#   • Provide thread-safe APIs to drain framed lines (read_lines) and to read
#     until a prompt-like line is observed (read_until_prompt).
#
# Design
#   • Exactly one reader thread per transport instance drains the OS buffer and
#     performs line framing. This prevents missed lines at higher rates and
#     keeps upper layers independent of pyserial blocking semantics.
#   • Line termination and prompt detection are read from console settings to
#     match the active console/monitor configuration.
# =============================================================================

from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

try:
    import serial  # pyserial
except Exception:
    serial = None

# Console-owned I/O knobs (terminator, timeouts, prompt regex)
from fi.console import console_settings as cs
from fi.console import console_styling as sty


@dataclass
class SerialConfig:
    """
    Immutable serial configuration used by SemTransport. Higher layers pass this
    in so the transport remains free of CLI parsing concerns.
    """
    device: str
    baud: int
    debug: bool = False


class SemTransport:
    """
    Serial transport with:
      • start_reader(): spawns a background thread that frames CR/LF lines.
      • write_line(text): writes a full line using the configured terminator.
      • read_lines(timeout_s): drains framed lines within a timeout window.
      • read_until_prompt(timeout_s): drains lines until a prompt-like line.
    The writer never blocks on the background reader; only the OS buffer limits
    apply to writes.
    """

    def __init__(self, cfg: SerialConfig) -> None:
        self._cfg = cfg
        self._ser: Optional["serial.Serial"] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._rx_stop = threading.Event()

        # Framed line queue and synchronization primitives
        self._lines: Deque[str] = deque()
        self._cv = threading.Condition()

        # Byte buffer for framing and last read time (used by prompt gating)
        self._buf = bytearray()
        self._last_rx_monotonic = time.monotonic()

        # Compile prompt detector (used by read_until_prompt)
        self._re_prompt = re.compile(getattr(cs, "PROMPT_REGEX", r"^[IOD]>\s*$"))

    # ---------------------------- lifecycle -----------------------------------
    def open(self) -> None:
        """Open the serial port with timeouts controlled by console settings."""
        if serial is None and not self._cfg.debug:
            raise RuntimeError("pyserial not available")
        
        try:
            if self._cfg.debug:
                # Import stub serial for debug mode
                from fi.backend.common.serial_stub import StubSerial
                
                self._ser = StubSerial(
                    port=self._cfg.device,
                    baudrate=self._cfg.baud,
                    timeout=float(getattr(cs, "READ_TIMEOUT_S", 0.05)),
                    write_timeout=float(getattr(cs, "WRITE_TIMEOUT_S", 0.10)),
                )
                # StubSerial needs explicit open
                if not self._ser.is_open:
                    self._ser.open()
            else:
                # Real serial connection
                self._ser = serial.Serial(
                    port=self._cfg.device,
                    baudrate=self._cfg.baud,
                    timeout=float(getattr(cs, "READ_TIMEOUT_S", 0.05)),
                    write_timeout=float(getattr(cs, "WRITE_TIMEOUT_S", 0.10)),
                )
            
            # Optional settle window after open
            open_delay = float(getattr(cs, "OPEN_TIMEOUT_S", 0.0))
            if open_delay > 0.0:
                time.sleep(open_delay)
                
        except Exception as e:
            raise RuntimeError(f"Failed to open {self._cfg.device} @ {self._cfg.baud}: {e}")


    def close(self) -> None:
        """Stop the reader thread (if running) and close the serial port."""
        self._rx_stop.set()
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=0.5)
        self._rx_thread = None
        if self._ser is not None:
            try:
                self._ser.close()
            finally:
                self._ser = None

    # ---------------------------- writer --------------------------------------
    def write_line(self, text: str) -> None:
        """
        Write a single command line to the UART, appending the configured
        terminator if the caller did not include it.
        """
        if self._ser is None:
            raise RuntimeError("Serial port not open")
        term = getattr(cs, "CR_TERMINATOR", "\r")
        payload = text if text.endswith(term) else (text + term)
        data = payload.encode("ascii", errors="ignore")
        n = self._ser.write(data)
        if n != len(data):
            raise RuntimeError("Short write on serial port")

    def write_bytes(self, data: bytes) -> None:
        """
        Write raw bytes to the UART without any terminator or encoding.
        
        This method is used for binary protocol commands (e.g., register injection)
        where line termination is not desired. Unlike write_line(), this method
        sends the exact bytes provided without modification.
        
        Args:
            data: Raw bytes to transmit
        
        Raises:
            RuntimeError: If serial port is not open or write fails
        """
        if self._ser is None:
            raise RuntimeError("Serial port not open")
        n = self._ser.write(data)
        if n != len(data):
            raise RuntimeError("Short write on serial port")


    # ---------------------------- reader --------------------------------------
    def start_reader(self) -> None:
        """
        Start the background reader if not already running. The reader drains
        pyserial, performs line framing on CR or LF, and enqueues decoded lines.
        """
        if self._rx_thread and self._rx_thread.is_alive():
            return
        self._rx_stop.clear()
        self._rx_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._rx_thread.start()

    def read_lines(self, *, timeout_s: float = 0.03) -> List[str]:
        """
        Drain any framed lines accumulated by the background reader. If the
        queue is empty, wait up to timeout_s for new lines to arrive.
        """
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        out: List[str] = []
        with self._cv:
            while True:
                while self._lines:
                    out.append(self._lines.popleft())
                if out:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._cv.wait(timeout=remaining)
        return out

    def read_until_prompt(self, *, timeout_s: float = 0.5) -> List[str]:
        """
        Drain framed lines until a prompt-like line is seen or the timeout
        expires. Returns every collected line, including the prompt if found.
        This is used by helpers that perform short state transitions.
        """
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        out: List[str] = []
        while time.monotonic() < deadline:
            lines = self.read_lines(timeout_s=0.05)
            if not lines:
                continue
            out.extend(lines)
            if any(self._re_prompt.match(ln) for ln in lines):
                break
        return out

    # ---------------------------- internals -----------------------------------
    def _reader_loop(self) -> None:
        """
        Continuously read from the UART and frame lines. This is the single
        consumer of the OS receive buffer, ensuring ordered processing and
        preventing lost data when upper layers momentarily stall.
        """
        ser = self._ser
        if ser is None:
            return

        term_cr = b"\r"
        term_lf = b"\n"

        while not self._rx_stop.is_set():
            try:
                chunk = ser.read(1024)
            except Exception:
                # Treat transient I/O errors as end-of-stream for safety.
                break
            if not chunk:
                continue

            self._buf.extend(chunk)
            self._last_rx_monotonic = time.monotonic()

            # Frame on CR or LF; ignore empty lines and strip trailing CR/LF.
            while True:
                cr_idx = self._buf.find(term_cr)
                lf_idx = self._buf.find(term_lf)
                # Choose earliest terminator found (if any)
                idxs = [i for i in (cr_idx, lf_idx) if i != -1]
                if not idxs:
                    break
                cut = min(idxs)
                line = self._buf[:cut].decode("ascii", errors="ignore")
                # Drop the terminator and any paired CRLF
                drop = 1
                if cut + 1 < len(self._buf) and self._buf[cut] in (term_cr[0], term_lf[0]) and self._buf[cut+1] in (term_cr[0], term_lf[0]):
                    drop = 2
                # Remove consumed bytes
                del self._buf[:cut + drop]
                if line.strip() == "":
                    continue
                with self._cv:
                    self._lines.append(line)
                    self._cv.notify_all()

    # ---------------------------- helpers -------------------------------------
    def is_open(self) -> bool:
        """Return True if the underlying serial port is currently open."""
        return self._ser is not None
