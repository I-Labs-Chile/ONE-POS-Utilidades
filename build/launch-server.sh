#!/bin/bash
# Script launcher para el ejecutable compilado
# Abre una terminal con los logs del servidor

# Obtener el directorio donde está el script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Cambiar al directorio del ejecutable
cd "$SCRIPT_DIR"

# Detectar qué emulador de terminal está disponible
if command -v gnome-terminal &> /dev/null; then
    # GNOME Terminal (Ubuntu, Fedora, etc.)
    gnome-terminal -- bash -c "echo '╔═══════════════════════════════════════════════╗'; echo '║  Servidor de Impresión ESC/POS - Q-Cube      ║'; echo '║  Logs en tiempo real                          ║'; echo '╚═══════════════════════════════════════════════╝'; echo ''; echo 'Iniciando servidor...'; echo ''; ./escpos-server; echo ''; echo '═══════════════════════════════════════════════'; echo 'El servidor se ha detenido.'; echo 'Presiona Enter para cerrar esta ventana...'; read"
elif command -v konsole &> /dev/null; then
    # KDE Konsole
    konsole --hold -e bash -c "echo '╔═══════════════════════════════════════════════╗'; echo '║  Servidor de Impresión ESC/POS - Q-Cube      ║'; echo '║  Logs en tiempo real                          ║'; echo '╚═══════════════════════════════════════════════╝'; echo ''; echo 'Iniciando servidor...'; echo ''; ./escpos-server"
elif command -v xfce4-terminal &> /dev/null; then
    # XFCE Terminal
    xfce4-terminal --hold -e "bash -c \"echo '╔═══════════════════════════════════════════════╗'; echo '║  Servidor de Impresión ESC/POS - Q-Cube      ║'; echo '║  Logs en tiempo real                          ║'; echo '╚═══════════════════════════════════════════════╝'; echo ''; echo 'Iniciando servidor...'; echo ''; ./escpos-server\""
elif command -v mate-terminal &> /dev/null; then
    # MATE Terminal
    mate-terminal -- bash -c "echo '╔═══════════════════════════════════════════════╗'; echo '║  Servidor de Impresión ESC/POS - Q-Cube      ║'; echo '║  Logs en tiempo real                          ║'; echo '╚═══════════════════════════════════════════════╝'; echo ''; echo 'Iniciando servidor...'; echo ''; ./escpos-server; echo ''; echo '═══════════════════════════════════════════════'; echo 'El servidor se ha detenido.'; echo 'Presiona Enter para cerrar esta ventana...'; read"
elif command -v x-terminal-emulator &> /dev/null; then
    # Terminal genérico de Debian/Ubuntu
    x-terminal-emulator -e bash -c "echo '╔═══════════════════════════════════════════════╗'; echo '║  Servidor de Impresión ESC/POS - Q-Cube      ║'; echo '║  Logs en tiempo real                          ║'; echo '╚═══════════════════════════════════════════════╝'; echo ''; echo 'Iniciando servidor...'; echo ''; ./escpos-server; echo ''; echo '═══════════════════════════════════════════════'; echo 'El servidor se ha detenido.'; echo 'Presiona Enter para cerrar esta ventana...'; read"
else
    # Fallback: intentar con xterm
    xterm -hold -e "bash -c \"echo '╔═══════════════════════════════════════════════╗'; echo '║  Servidor de Impresión ESC/POS - Q-Cube      ║'; echo '║  Logs en tiempo real                          ║'; echo '╚═══════════════════════════════════════════════╝'; echo ''; echo 'Iniciando servidor...'; echo ''; ./escpos-server\""
fi
