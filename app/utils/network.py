# -*- coding: utf-8 -*-
# Utilidades de red para obtener la IP local

import socket

def get_primary_ip() -> str:
    # Obtiene la IP local primaria intentando conectar a un destino público
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "0.0.0.0"
