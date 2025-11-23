import asyncio
import logging
from datetime import datetime
from typing import Optional, List
import io

logger = logging.getLogger(__name__)

class LogPrinter:
    
    def __init__(self, printer_backend=None):
        self.printer_backend = printer_backend
        self.enabled = False
        self.log_levels = ['INFO', 'WARNING', 'ERROR']
        self.max_line_length = 32  # Para impresoras de 58mm
        
        # ESC/POS commands
        self.ESC = b'\x1b'
        self.GS = b'\x1d'
        
    def set_printer_backend(self, printer_backend):
        self.printer_backend = printer_backend
        
    def enable(self, log_levels: Optional[List[str]] = None):
        self.enabled = True
        if log_levels:
            self.log_levels = log_levels
        logger.info(f"Log printing enabled for levels: {self.log_levels}")
        
    def disable(self):
        self.enabled = False
        logger.info("Log printing disabled")
        
    async def print_log(self, level: str, message: str, module: str = ""):

        if not self.enabled or not self.printer_backend:
            return
            
        if level not in self.log_levels:
            return
            
        try:
            # Create formatted log entry
            escpos_data = self._create_log_entry(level, message, module)
            
            # Send to printer
            await self.printer_backend.send_raw(escpos_data)
            
        except Exception as e:
            # Don't log this error to avoid recursion
            print(f"Failed to print log to printer: {e}")
    
    def _create_log_entry(self, level: str, message: str, module: str = "") -> bytes:

        output = io.BytesIO()
        
        # Initialize printer
        output.write(self.ESC + b'@')
        
        # Set character set to PC850 (Spanish characters)
        output.write(self.ESC + b't' + b'\x13')
        
        # Header with timestamp and level
        timestamp = datetime.now().strftime("%H:%M:%S")
        header = f"[{timestamp}] {level}"
        
        if module:
            header += f" {module[:8]}"  # Truncate module name
            
        # Print header in bold
        output.write(self.ESC + b'E\x01')  # Bold on
        output.write(self._wrap_text(header).encode('cp850', errors='replace'))
        output.write(self.ESC + b'E\x00')  # Bold off
        output.write(b'\n')
        
        # Print message
        wrapped_message = self._wrap_text(message)
        output.write(wrapped_message.encode('cp850', errors='replace'))
        output.write(b'\n')
        
        # Add separator for important messages
        if level in ['WARNING', 'ERROR']:
            output.write(b'-' * self.max_line_length + b'\n')
        
        # Feed extra line
        output.write(b'\n')
        
        return output.getvalue()
    
    def _wrap_text(self, text: str) -> str:

        if len(text) <= self.max_line_length:
            return text
            
        lines = []
        words = text.split(' ')
        current_line = ""
        
        for word in words:
            if len(current_line + word + " ") <= self.max_line_length:
                current_line += word + " "
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word + " "
                
        if current_line:
            lines.append(current_line.strip())
            
        return '\n'.join(lines)
    
    async def print_startup_banner(self, server_info: dict):

        if not self.enabled or not self.printer_backend:
            return
            
        try:
            output = io.BytesIO()
            
            # Initialize printer
            output.write(self.ESC + b'@')
            
            # Center align
            output.write(self.ESC + b'a\x01')
            
            # Print banner in enlarged text
            output.write(self.GS + b'!\x11')  # Double height and width
            output.write(b'ONE-POS\n')
            output.write(self.GS + b'!\x00')  # Normal size
            
            output.write(b'Print Server\n')
            output.write(f"v{server_info.get('version', '1.0')}\n".encode())
            
            # Left align for details
            output.write(self.ESC + b'a\x00')
            output.write(b'\n')
            
            # Server details
            output.write(f"Host: {server_info.get('host', 'localhost')}\n".encode())
            output.write(f"Port: {server_info.get('port', 631)}\n".encode())
            output.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n".encode())
            
            # Add separator
            output.write(b'=' * self.max_line_length + b'\n\n')
            
            await self.printer_backend.send_raw(output.getvalue())
            
        except Exception as e:
            print(f"Failed to print startup banner: {e}")
    
    async def print_status_report(self, status_info: dict):

        if not self.enabled or not self.printer_backend:
            return
            
        try:
            output = io.BytesIO()
            
            # Initialize printer
            output.write(self.ESC + b'@')
            
            # Title
            output.write(self.ESC + b'E\x01')  # Bold
            output.write(b'STATUS REPORT\n')
            output.write(self.ESC + b'E\x00')  # Normal
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output.write(f"Time: {timestamp}\n".encode())
            output.write(b'-' * self.max_line_length + b'\n')
            
            # Printer status
            if 'printer' in status_info:
                printer = status_info['printer']
                output.write(b'PRINTER:\n')
                output.write(f"Connected: {printer.get('connected', 'Unknown')}\n".encode())
                if printer.get('device_info'):
                    output.write(f"Device: {printer['device_info']}\n".encode())
            
            # Job statistics
            if 'jobs' in status_info:
                jobs = status_info['jobs']
                output.write(b'\nJOBS:\n')
                output.write(f"Active: {jobs.get('active', 0)}\n".encode())
                output.write(f"Completed: {jobs.get('completed', 0)}\n".encode())
                output.write(f"Failed: {jobs.get('failed', 0)}\n".encode())
            
            output.write(b'\n' + b'=' * self.max_line_length + b'\n\n')
            
            await self.printer_backend.send_raw(output.getvalue())
            
        except Exception as e:
            print(f"Failed to print status report: {e}")

# Custom logging handler for printing logs to printer
class PrinterLogHandler(logging.Handler):
    
    def __init__(self, log_printer: LogPrinter):
        super().__init__()
        self.log_printer = log_printer
        self.loop = None
        
    def emit(self, record):
        if self.log_printer and self.log_printer.enabled:
            try:
                # Get or create event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return  # No event loop, skip
                
                # Schedule the print task
                asyncio.create_task(
                    self.log_printer.print_log(
                        record.levelname,
                        record.getMessage(),
                        record.name
                    )
                )
            except Exception:
                pass  # Silently ignore errors to avoid recursion