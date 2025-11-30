import asyncio
import logging
from datetime import datetime
from typing import Optional, List
import io

logger = logging.getLogger(__name__)

# Impresor de logs en formato ESC/POS para tickets
class LogPrinter:
    
    def __init__(self, printer_backend=None):
        self.printer_backend = printer_backend
        self.enabled = False
        self.log_levels = ['INFO', 'WARNING', 'ERROR']
        self.max_line_length = 32  # Impresoras de 58mm
        
        # Comandos ESC/POS
        self.ESC = b'\x1b'
        self.GS = b'\x1d'
        
    # Asigna el backend de impresión a utilizar
    def set_printer_backend(self, printer_backend):
        self.printer_backend = printer_backend
        
    # Habilita la impresión de logs; niveles posibles: ['INFO','WARNING','ERROR']
    def enable(self, log_levels: Optional[List[str]] = None):
        self.enabled = True
        if log_levels:
            self.log_levels = log_levels
        logger.info(f"Impresión de logs habilitada para niveles: {self.log_levels}")
        
    # Deshabilita la impresión de logs
    def disable(self):
        self.enabled = False
        logger.info("Impresión de logs deshabilitada")
        
    # Imprime un log con nivel y mensaje; módulo opcional para identificar origen
    async def print_log(self, level: str, message: str, module: str = ""):

        if not self.enabled or not self.printer_backend:
            return
            
        if level not in self.log_levels:
            return
            
        try:
            # Crear entrada formateada
            escpos_data = self._create_log_entry(level, message, module)
            
            # Enviar a impresora
            await self.printer_backend.send_raw(escpos_data)
            
        except Exception as e:
            # Evitar recursión de logs
            print(f"Fallo al imprimir log en impresora: {e}")
    
    # Genera bytes ESC/POS con encabezado y mensaje envueltos a ancho de papel
    def _create_log_entry(self, level: str, message: str, module: str = "") -> bytes:

        output = io.BytesIO()
        
        # Inicializar impresora
        output.write(self.ESC + b'@')
        
        # Conjunto de caracteres PC850 (soporta español)
        output.write(self.ESC + b't' + b'\x13')
        
        # Encabezado con hora y nivel
        timestamp = datetime.now().strftime("%H:%M:%S")
        header = f"[{timestamp}] {level}"
        
        if module:
            header += f" {module[:8]}"  # Truncar nombre de módulo
            
        # Imprimir encabezado en negrita
        output.write(self.ESC + b'E\x01')  # Negrita ON
        output.write(self._wrap_text(header).encode('cp850', errors='replace'))
        output.write(self.ESC + b'E\x00')  # Negrita OFF
        output.write(b'\n')
        
        # Imprimir mensaje
        wrapped_message = self._wrap_text(message)
        output.write(wrapped_message.encode('cp850', errors='replace'))
        output.write(b'\n')
        
        # Separador para mensajes importantes
        if level in ['WARNING', 'ERROR']:
            output.write(b'-' * self.max_line_length + b'\n')
        
        # Alimentación extra
        output.write(b'\n')
        
        return output.getvalue()
    
    # Envuelve texto al ancho máximo de línea conservando palabras
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
    
    # Imprime un banner de inicio con información del servidor (host, puerto, versión)
    async def print_startup_banner(self, server_info: dict):

        if not self.enabled or not self.printer_backend:
            return
            
        try:
            output = io.BytesIO()
            
            # Inicializar
            output.write(self.ESC + b'@')
            
            # Centrar
            output.write(self.ESC + b'a\x01')
            
            # Texto grande
            output.write(self.GS + b'!\x11')  # Doble alto y ancho
            output.write(b'ONE-POS\n')
            output.write(self.GS + b'!\x00')  # Tamaño normal
            
            output.write(b'Print Server\n')
            output.write(f"v{server_info.get('version', '1.0')}\n".encode())
            
            # Alinear a la izquierda
            output.write(self.ESC + b'a\x00')
            output.write(b'\n')
            
            # Detalles
            output.write(f"Host: {server_info.get('host', 'localhost')}\n".encode())
            output.write(f"Puerto: {server_info.get('port', 631)}\n".encode())
            output.write(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n".encode())
            
            # Separador
            output.write(b'=' * self.max_line_length + b'\n\n')
            
            await self.printer_backend.send_raw(output.getvalue())
            
        except Exception as e:
            print(f"Fallo al imprimir banner de inicio: {e}")
    
    # Imprime un reporte de estado con métricas básicas (impresora y trabajos)
    async def print_status_report(self, status_info: dict):

        if not self.enabled or not self.printer_backend:
            return
            
        try:
            output = io.BytesIO()
            
            # Inicializar
            output.write(self.ESC + b'@')
            
            # Título
            output.write(self.ESC + b'E\x01')  # Negrita
            output.write(b'REPORTE DE ESTADO\n')
            output.write(self.ESC + b'E\x00')  # Normal
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output.write(f"Hora: {timestamp}\n".encode())
            output.write(b'-' * self.max_line_length + b'\n')
            
            # Estado de impresora
            if 'printer' in status_info:
                printer = status_info['printer']
                output.write(b'IMPRESORA:\n')
                output.write(f"Conectada: {printer.get('connected', 'Desconocido')}\n".encode())
                if printer.get('device_info'):
                    output.write(f"Dispositivo: {printer['device_info']}\n".encode())
            
            # Estadísticas de trabajos
            if 'jobs' in status_info:
                jobs = status_info['jobs']
                output.write(b'\nTRABAJOS:\n')
                output.write(f"Activos: {jobs.get('active', 0)}\n".encode())
                output.write(f"Completados: {jobs.get('completed', 0)}\n".encode())
                output.write(f"Fallidos: {jobs.get('failed', 0)}\n".encode())
            
            output.write(b'\n' + b'=' * self.max_line_length + b'\n\n')
            
            await self.printer_backend.send_raw(output.getvalue())
            
        except Exception as e:
            print(f"Fallo al imprimir reporte de estado: {e}")

# Handler de logging que envía registros a la impresora
class PrinterLogHandler(logging.Handler):
    
    def __init__(self, log_printer: LogPrinter):
        super().__init__()
        self.log_printer = log_printer
        self.loop = None
        
    # Emite un registro de logging hacia la impresora si está habilitado
    def emit(self, record):
        if self.log_printer and self.log_printer.enabled:
            try:
                # Obtener o verificar loop de eventos activo
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return  # Sin loop, se omite
                
                # Programar tarea de impresión
                asyncio.create_task(
                    self.log_printer.print_log(
                        record.levelname,
                        record.getMessage(),
                        record.name
                    )
                )
            except Exception:
                pass  # Silenciar para evitar recursión