from typing import List, Optional, Dict, Tuple
import subprocess
import platform
import logging
import socket
import psutil
import time
import sys

logger = logging.getLogger(__name__)

class PortManager:
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.preferred_ports = [631, 8631, 8632, 9100, 9101]
        
    # Verifica si un puerto está disponible para bind en el host dado.
    # Parámetros: port (int), host (str, por defecto 'localhost').
    # Retorno: True si el bind es posible; False si está ocupado o hubo error.
    def is_port_available(self, port: int, host: str = 'localhost') -> bool:

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                # Configurar opciones de socket
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # En Linux/Unix, también usar SO_REUSEPORT si está disponible
                if hasattr(socket, 'SO_REUSEPORT') and self.platform in ['linux', 'darwin']:
                    try:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    except OSError:
                        pass  # No soportado en esta versión
                
                result = s.bind((host, port))
                return True
                
        except OSError as e:
            # Puerto ocupado o error de bind
            return False
        except Exception:
            return False
    
    # Obtiene procesos que están usando un puerto específico.
    # Parámetros: port (int).
    # Retorno: lista de dicts con información del proceso (pid, nombre, estado, dirección).
    def get_process_using_port(self, port: int) -> List[Dict[str, str]]:

        processes = []
        
        try:
            # Usar psutil (multiplataforma)
            for conn in psutil.net_connections():
                if conn.laddr and conn.laddr.port == port:
                    try:
                        proc = psutil.Process(conn.pid) if conn.pid else None
                        process_info = {
                            'pid': conn.pid,
                            'name': proc.name() if proc else 'Unknown',
                            'status': conn.status,
                            'address': f"{conn.laddr.ip}:{conn.laddr.port}"
                        }
                        processes.append(process_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
        except Exception as e:
            logger.warning(f"No se pudo obtener información de procesos: {e}")
            
            # Fallback usando comandos del sistema
            try:
                if self.platform == 'windows':
                    processes = self._get_process_windows(port)
                else:
                    processes = self._get_process_unix(port)
            except Exception:
                pass
        
        return processes
    
    # Fallback para Windows: obtiene procesos escuchando en el puerto vía netstat.
    # Parámetros: port (int).
    # Retorno: lista de dicts con (pid, nombre, estado, dirección).
    def _get_process_windows(self, port: int) -> List[Dict[str, str]]:
        try:
            result = subprocess.run(['netstat', '-ano'], 
                                  capture_output=True, text=True, timeout=5)
            
            processes = []
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            proc = psutil.Process(int(pid))
                            processes.append({
                                'pid': pid,
                                'name': proc.name(),
                                'status': 'LISTENING',
                                'address': parts[1]
                            })
                        except (ValueError, psutil.NoSuchProcess):
                            processes.append({
                                'pid': pid,
                                'name': 'Unknown',
                                'status': 'LISTENING',
                                'address': parts[1]
                            })
            return processes
        except Exception:
            return []
    
    # Fallback para Unix: intenta con lsof y luego netstat para listar procesos en el puerto.
    # Parámetros: port (int).
    # Retorno: lista de dicts con (pid, nombre, estado, dirección).
    def _get_process_unix(self, port: int) -> List[Dict[str, str]]:
        processes = []
        
        # Intentar con lsof primero
        try:
            result = subprocess.run(['lsof', '-i', f':{port}'], 
                                  capture_output=True, text=True, timeout=5)
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 2:
                        processes.append({
                            'pid': parts[1],
                            'name': parts[0],
                            'status': 'LISTENING',
                            'address': parts[-1] if len(parts) > 8 else f'*:{port}'
                        })
            return processes
        except Exception:
            pass
        
        # Fallback a netstat
        try:
            result = subprocess.run(['netstat', '-tlnp'], 
                                  capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTEN' in line:
                    processes.append({
                        'pid': 'Unknown',
                        'name': 'Unknown',
                        'status': 'LISTENING',
                        'address': line.split()[3]
                    })
            return processes
        except Exception:
            return []
    
    # Encuentra un puerto disponible siguiendo preferencia y rangos.
    # Parámetros: preferred_port (int opcional), start_range (int), end_range (int).
    # Retorno: int del puerto libre o None si no hay disponibilidad.
    def find_available_port(self, preferred_port: Optional[int] = None, 
                           start_range: int = 8631, end_range: int = 8700) -> Optional[int]:

        # Intentar puerto preferido primero
        if preferred_port and self.is_port_available(preferred_port):
            return preferred_port
        
        # Intentar puertos estándar
        for port in self.preferred_ports:
            if port != preferred_port and self.is_port_available(port):
                return port
        
        # Buscar en el rango especificado
        for port in range(start_range, end_range + 1):
            if self.is_port_available(port):
                return port
        
        return None
    
    # Intenta detener servicios conocidos que ocupan el puerto.
    # Parámetros: port (int), service_names (lista de nombres de servicio).
    # Retorno: True si algún servicio fue detenido, False en caso contrario.
    def stop_service_on_port(self, port: int, service_names: List[str] = None) -> bool:

        if service_names is None:
            service_names = ['cups', 'cupsd', 'cups-browsed']
        
        processes = self.get_process_using_port(port)
        
        for process in processes:
            process_name = process.get('name', '').lower()
            
            # Si es un servicio conocido, intentar detenerlo
            if any(service in process_name for service in service_names):
                return self._stop_system_service(process_name, process.get('pid'))
        
        return False
    
    # Detiene un servicio del sistema según la plataforma.
    # Parámetros: service_name (str), pid (str opcional).
    # Retorno: True si se detuvo correctamente; False si no fue posible.
    def _stop_system_service(self, service_name: str, pid: str = None) -> bool:

        try:
            if self.platform == 'windows':
                # Windows: usar sc stop
                result = subprocess.run(['sc', 'stop', service_name], 
                                      capture_output=True, timeout=10)
                return result.returncode == 0
                
            elif self.platform in ['linux', 'darwin']:
                # Linux/macOS: usar systemctl si está disponible
                if service_name in ['cups', 'cupsd']:
                    try:
                        subprocess.run(['sudo', 'systemctl', 'stop', 'cups'], 
                                     timeout=10, check=True)
                        subprocess.run(['sudo', 'systemctl', 'stop', 'cups-browsed'], 
                                     timeout=10, capture_output=True)
                        return True
                    except subprocess.CalledProcessError:
                        pass
                    
                    # Fallback: intentar pkill
                    try:
                        subprocess.run(['sudo', 'pkill', 'cupsd'], 
                                     timeout=5, capture_output=True)
                        return True
                    except subprocess.CalledProcessError:
                        pass
            
            return False
            
        except Exception as e:
            logger.warning(f"No se pudo detener el servicio {service_name}: {e}")
            return False
    
    # Crea un socket de servidor con opciones de reutilización.
    # Parámetros: host (str), port (int), reuse_port (bool).
    # Retorno: socket listo para bind; puede lanzar excepción en caso de error.
    def create_server_socket(self, host: str, port: int, reuse_port: bool = True) -> socket.socket:

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # SO_REUSEADDR (disponible en todas las plataformas)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # SO_REUSEPORT (Linux 3.9+, FreeBSD, macOS)
            if (reuse_port and hasattr(socket, 'SO_REUSEPORT') and 
                self.platform in ['linux', 'darwin', 'freebsd']):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    logger.debug("SO_REUSEPORT enabled")
                except OSError as e:
                    logger.debug(f"SO_REUSEPORT no disponible: {e}")
            
            # En Windows, configurar opciones específicas
            if self.platform == 'windows':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 0)
            
            sock.bind((host, port))
            return sock
            
        except Exception:
            sock.close()
            raise
    
    # Obtiene información básica del sistema y red local.
    # Retorno: dict con hostname, IP local y plataforma.
    def get_network_info(self) -> Dict[str, str]:

        info = {
            'hostname': 'localhost',
            'local_ip': 'localhost',
            'platform': self.platform
        }
        
        try:
            # Hostname
            info['hostname'] = socket.gethostname()
            
            # IP local
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(1)
                s.connect(("8.8.8.8", 80))
                info['local_ip'] = s.getsockname()[0]
                
        except Exception:
            try:
                # Fallback
                info['local_ip'] = socket.gethostbyname(socket.gethostname())
            except Exception:
                pass
        
        return info