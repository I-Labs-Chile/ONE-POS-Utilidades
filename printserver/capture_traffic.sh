#!/bin/bash

# Crear directorio de logs
mkdir -p debug_logs

echo "🕵️  Iniciando captura de tráfico IPP..."
echo "Puerto 631 - Modo debugging activado"

# Capturar tráfico en puerto 631
sudo tcpdump -i any -s 65535 -w debug_logs/ipp_traffic_$(date +%Y%m%d_%H%M%S).pcap \
    "port 631" &

TCPDUMP_PID=$!

echo "📡 Captura de tráfico iniciada (PID: $TCPDUMP_PID)"
echo "🔍 Archivos se guardarán en debug_logs/"
echo ""
echo "Instrucciones:"
echo "1. Deja este script corriendo"
echo "2. Conecta desde Android e intenta imprimir"
echo "3. Conecta desde PC e intenta imprimir"
echo "4. Presiona Ctrl+C para parar la captura"
echo ""
echo "💡 Usa Wireshark para analizar los archivos .pcap generados"

# Función para cleanup al recibir Ctrl+C
cleanup() {
    echo ""
    echo "🛑 Parando captura de tráfico..."
    sudo kill $TCPDUMP_PID 2>/dev/null
    echo "✅ Captura completada. Archivos en debug_logs/"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT

# Esperar indefinidamente
wait $TCPDUMP_PID