#!/bin/bash
# Lanza la Cabina Fotográfica (escpos-cabina) con logs visibles en una terminal.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BANNER="echo '╔═══════════════════════════════════════╗'; echo '║   CABINA FOTOGRÁFICA ONE-POS          ║'; echo '╚═══════════════════════════════════════╝';"

if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "$BANNER echo ''; ./escpos-cabina; echo ''; echo 'Presiona Enter para cerrar...'; read"
elif command -v konsole &> /dev/null; then
    konsole --hold -e bash -c "$BANNER echo ''; ./escpos-cabina"
elif command -v xfce4-terminal &> /dev/null; then
    xfce4-terminal --hold -e "bash -c \"$BANNER echo ''; ./escpos-cabina\""
elif command -v mate-terminal &> /dev/null; then
    mate-terminal -- bash -c "$BANNER echo ''; ./escpos-cabina; echo ''; echo 'Presiona Enter para cerrar...'; read"
else
    xterm -hold -e "bash -c \"$BANNER echo ''; ./escpos-cabina\""
fi
