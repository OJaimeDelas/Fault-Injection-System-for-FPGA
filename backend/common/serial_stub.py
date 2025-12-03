# =============================================================================
# FATORI-V • FI Backend
# File: serial_stub.py
# -----------------------------------------------------------------------------
# Serial port stub for debug mode (simulates hardware responses).
#=============================================================================

import time


class StubSerial:
    """
    Serial port stub that simulates hardware without actual connection.
    
    This mimics pyserial's Serial interface but fakes all I/O operations.
    Used in debug mode to allow full campaign execution without hardware.
    
    The stub is SILENT - it doesn't log anything directly. All logging
    happens through the normal FI logging system at higher levels.
    
    The stub simulates realistic behavior:
    - Open/close operations
    - Read/write with appropriate delays
    - Realistic response bytes (success codes)
    - Proper timeouts
    
    This allows testing the entire injection stack without the board.
    """
    
    def __init__(self, port, baudrate, timeout=1.0, write_timeout=None, **kwargs):
        """
        Initialize stub serial port.
        
        Args:
            port: Port name (e.g., "/dev/ttyUSB0") - not actually used
            baudrate: Baud rate - used for delay simulation
            timeout: Read timeout in seconds
            write_timeout: Write timeout in seconds
            **kwargs: Other serial parameters (ignored)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self._is_open = False
        self._write_count = 0
        self._read_count = 0
    
    def open(self):
        """Simulate opening serial port."""
        if self._is_open:
            raise Exception(f"Port {self.port} already open")
        self._is_open = True
    
    def close(self):
        """Simulate closing serial port."""
        if not self._is_open:
            return
        self._is_open = False
    
    @property
    def is_open(self):
        """Check if port is open."""
        return self._is_open
    
    def write(self, data):
        """
        Simulate writing data to serial port.
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes "written"
        """
        if not self._is_open:
            raise Exception("Port not open")
        
        self._write_count += 1
        
        # Simulate transmission time based on baud rate
        # At 1250000 baud: ~10 bits per byte → ~0.008ms per byte
        delay = len(data) * 10 / self.baudrate
        time.sleep(delay)
        
        return len(data)
    
    def read(self, size=1):
        """
        Simulate reading data from serial port.
        
        Returns success bytes (0x00) for all reads to simulate
        successful hardware responses.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Mock response bytes (all 0x00 = success)
        """
        if not self._is_open:
            raise Exception("Port not open")
        
        self._read_count += 1
        
        # Simulate realistic read delay
        # Assume data arrives at line rate
        delay = size * 10 / self.baudrate
        time.sleep(delay)
        
        # Return success bytes (0x00 indicates success in most protocols)
        response = b'\x00' * size
        
        return response
    
    def flush(self):
        """Simulate flushing buffers."""
        pass
    
    def reset_input_buffer(self):
        """Simulate clearing input buffer."""
        pass
    
    def reset_output_buffer(self):
        """Simulate clearing output buffer."""
        pass
    
    @property
    def in_waiting(self):
        """
        Simulate checking bytes available in input buffer.
        
        Returns:
            Always 0 (no data waiting)
        """
        return 0
    
    def __enter__(self):
        """Context manager entry."""
        if not self._is_open:
            self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()