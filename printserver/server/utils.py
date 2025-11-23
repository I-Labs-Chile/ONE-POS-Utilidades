import logging
import logging.handlers
import sys
import os
import asyncio
import signal
import json
from typing import Any, Dict, Optional, Callable
from datetime import datetime
import traceback

# Try relative import first, fallback to absolute
try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

# Global logger instance
logger = logging.getLogger(__name__)

def setup_logging(log_level: str = None, log_file: str = None) -> logging.Logger:

    # Determine log level
    level = log_level or settings.LOG_LEVEL
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file or settings.LOG_FILE:
        file_path = log_file or settings.LOG_FILE
        try:
            # Ensure log directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Rotating file handler to prevent huge log files
            file_handler = logging.handlers.RotatingFileHandler(
                file_path, maxBytes=10*1024*1024, backupCount=5
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            logger.info(f"Logging to file: {file_path}")
            
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")
    
    # Configure aiohttp access logger specifically
    aiohttp_access_logger = logging.getLogger('aiohttp.access')
    aiohttp_access_logger.setLevel(logging.INFO)
    
    logger.info(f"Logging initialized - Level: {level}")
    return root_logger

def validate_configuration() -> bool:
    logger.info("Validating configuration...")
    
    try:
        errors = settings.validate_config()
        
        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation error: {e}")
        return False

def get_system_info() -> Dict[str, Any]:
    import platform
    import socket
    
    try:
        info = {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'hostname': socket.gethostname(),
            'server_version': settings.VERSION,
            'build_date': settings.BUILD_DATE
        }
        
        # Add network interfaces
        try:
            import psutil
            interfaces = {}
            for interface, addrs in psutil.net_if_addrs().items():
                interface_info = []
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        interface_info.append({
                            'family': 'IPv4',
                            'address': addr.address,
                            'netmask': addr.netmask,
                            'broadcast': addr.broadcast
                        })
                if interface_info:
                    interfaces[interface] = interface_info
            info['network_interfaces'] = interfaces
        except ImportError:
            # psutil not available
            pass
        
        return info
        
    except Exception as e:
        logger.warning(f"Error getting system info: {e}")
        return {'error': str(e)}

def create_status_report(printer_backend=None, converter=None, ipp_server=None) -> Dict[str, Any]:
    report = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'server': {
            'name': settings.PRINTER_NAME,
            'version': settings.VERSION,
            'host': settings.SERVER_HOST,
            'port': settings.SERVER_PORT,
            'uri': settings.get_printer_uri()
        },
        'system': get_system_info(),
        'configuration': {
            'printer_width_mm': settings.PRINTER_WIDTH_MM,
            'printer_dpi': settings.PRINTER_DPI,
            'supported_formats': settings.SUPPORTED_FORMATS,
            'supported_operations': settings.SUPPORTED_OPERATIONS
        },
        'components': {}
    }

    if printer_backend:
        try:
            # Handle async get_printer_status properly
            if hasattr(printer_backend, 'get_printer_status'):
                if asyncio.iscoroutinefunction(printer_backend.get_printer_status):
                    # We can't await here in a sync function, so we'll get a simplified status
                    status = {'connected': hasattr(printer_backend, '_connected') and getattr(printer_backend, '_connected', False)}
                else:
                    status = printer_backend.get_printer_status()
            else:
                status = 'Unknown'
                
            report['components']['printer_backend'] = {
                'class': type(printer_backend).__name__,
                'status': status
            }
        except Exception as e:
            report['components']['printer_backend'] = {
                'class': type(printer_backend).__name__,
                'status': f'Error getting status: {e}'
            }

    if converter:
        report['components']['converter'] = {
            'supported_formats': converter.get_supported_formats()
        }

    if ipp_server:
        try:
            report['components']['ipp_server'] = {
                'is_running': ipp_server.is_running if hasattr(ipp_server, 'is_running') else False,
                'port': getattr(ipp_server, 'port', None),
                'active_jobs': len(ipp_server.active_jobs) if hasattr(ipp_server, 'active_jobs') else 0
            }
        except Exception as e:
            report['components']['ipp_server'] = {
                'is_running': False,
                'error': str(e)
            }
    
    return report

class SignalHandler:

    def __init__(self):
        self.shutdown_callbacks: list[Callable] = []
        self.shutdown_event = asyncio.Event()
        
    def add_shutdown_callback(self, callback: Callable):
        self.shutdown_callbacks.append(callback)
    
    def setup_signal_handlers(self):
        if sys.platform != 'win32':
            # Unix-like systems
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGHUP, self._signal_handler)
        else:
            # Windows
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self):
        await self.shutdown_event.wait()
        
        # Call shutdown callbacks
        for callback in self.shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in shutdown callback: {e}")

def format_bytes(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

class PerformanceMonitor:
    
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.timings: Dict[str, list] = {}
        self.start_time = datetime.utcnow()
    
    def increment_counter(self, name: str, value: int = 1):
        self.counters[name] = self.counters.get(name, 0) + value
    
    def record_timing(self, name: str, duration: float):
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(duration)
        
        # Keep only last 100 measurements
        if len(self.timings[name]) > 100:
            self.timings[name] = self.timings[name][-100:]
    
    def get_statistics(self) -> Dict[str, Any]:
        stats = {
            'uptime': (datetime.utcnow() - self.start_time).total_seconds(),
            'counters': dict(self.counters),
            'timings': {}
        }
        
        for name, times in self.timings.items():
            if times:
                stats['timings'][name] = {
                    'count': len(times),
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'recent_avg': sum(times[-10:]) / min(len(times), 10) if times else 0
                }
        
        return stats

# Global performance monitor
performance_monitor = PerformanceMonitor()

def safe_json_serialize(obj: Any) -> str:

    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return f"<bytes: {len(obj)} bytes>"
        elif hasattr(obj, '__dict__'):
            return f"<{obj.__class__.__name__} object>"
        else:
            return str(obj)
    
    try:
        return json.dumps(obj, default=json_serializer, indent=2)
    except Exception as e:
        return f"<JSON serialization error: {e}>"

async def health_check() -> Dict[str, Any]:
    health = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'status': 'healthy',
        'checks': {}
    }
    
    try:
        # Check configuration
        config_valid = validate_configuration()
        health['checks']['configuration'] = {
            'status': 'pass' if config_valid else 'fail',
            'message': 'Configuration valid' if config_valid else 'Configuration errors found'
        }
        
        # Check USB printer availability
        try:
            # Import with try/except to handle relative import issues
            try:
                from ..usb.usb_handler import list_usb_printers
            except ImportError:
                from usb.usb_handler import list_usb_printers
            
            printers = await list_usb_printers()
            health['checks']['usb_printers'] = {
                'status': 'pass' if printers else 'warn',
                'message': f'Found {len(printers)} USB printers',
                'count': len(printers)
            }
        except Exception as e:
            health['checks']['usb_printers'] = {
                'status': 'fail',
                'message': f'USB check failed: {e}'
            }
        
        # Check dependencies
        deps = check_dependencies()
        health['checks']['dependencies'] = {
            'status': 'pass' if deps['all_available'] else 'warn',
            'message': f"{deps['available_count']}/{deps['total_count']} dependencies available",
            'details': deps
        }
        
        # Overall health status
        failed_checks = [name for name, check in health['checks'].items() 
                        if check['status'] == 'fail']
        
        if failed_checks:
            health['status'] = 'unhealthy'
        elif any(check['status'] == 'warn' for check in health['checks'].values()):
            health['status'] = 'degraded'
        
    except Exception as e:
        health['status'] = 'unhealthy'
        health['error'] = str(e)
        logger.error(f"Health check failed: {e}")
    
    return health

def check_dependencies() -> Dict[str, Any]:
    dependencies = {
        'pyusb': False,
        'pillow': False,
        'ghostscript': False,
        'zeroconf': False,
        'aiohttp': False
    }
    
    # Check each dependency
    try:
        import usb.core
        dependencies['pyusb'] = True
    except ImportError:
        pass
    
    try:
        import PIL
        dependencies['pillow'] = True
    except ImportError:
        pass
    
    try:
        import subprocess
        subprocess.run(['gs', '--version'], capture_output=True, timeout=5)
        dependencies['ghostscript'] = True
    except (ImportError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    try:
        from zeroconf import Zeroconf
        dependencies['zeroconf'] = True
    except ImportError:
        pass
    
    try:
        import aiohttp
        dependencies['aiohttp'] = True
    except ImportError:
        pass
    
    available_count = sum(dependencies.values())
    total_count = len(dependencies)
    
    return {
        'dependencies': dependencies,
        'available_count': available_count,
        'total_count': total_count,
        'all_available': available_count == total_count,
        'missing': [name for name, available in dependencies.items() if not available]
    }

def log_exception(operation: str, exception: Exception):
    logger.error(f"{operation} failed: {exception}")
    logger.debug(f"Exception details:\n{traceback.format_exc()}")

# Decorator for timing operations
def timed_operation(operation_name: str):

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = asyncio.get_event_loop().time()
            try:
                result = await func(*args, **kwargs)
                performance_monitor.increment_counter(f"{operation_name}_success")
                return result
            except Exception as e:
                performance_monitor.increment_counter(f"{operation_name}_error")
                raise
            finally:
                duration = asyncio.get_event_loop().time() - start_time
                performance_monitor.record_timing(operation_name, duration)
        
        def sync_wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                performance_monitor.increment_counter(f"{operation_name}_success")
                return result
            except Exception as e:
                performance_monitor.increment_counter(f"{operation_name}_error")
                raise
            finally:
                duration = time.time() - start_time
                performance_monitor.record_timing(operation_name, duration)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator