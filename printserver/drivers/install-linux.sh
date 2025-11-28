#!/bin/bash
################################################################################
# ONE-POS Network Printer - Instalador Rápido para Linux (CUPS)
# 
# Este script instala automáticamente la impresora ONE-POS en CUPS
# 
# Uso:
#   sudo ./install-linux.sh [IP_SERVIDOR] [PUERTO]
#   
# Ejemplo:
#   sudo ./install-linux.sh 192.168.1.100 631
#   sudo ./install-linux.sh  # Usa localhost:631 por defecto
#
################################################################################

set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración
PRINTER_NAME="ONE-POS-Printer"
PRINTER_DESCRIPTION="ONE POS Network Printer"
PRINTER_LOCATION="Office"
PPD_FILE="ONEPOS-IPP.ppd"

# Parámetros (con valores por defecto)
SERVER_IP="${1:-localhost}"
SERVER_PORT="${2:-631}"
PRINTER_URI="ipp://${SERVER_IP}:${SERVER_PORT}/ipp/printer"

################################################################################
# Funciones auxiliares
################################################################################

print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                    ║${NC}"
    echo -e "${BLUE}║        ONE-POS Network Printer Installer          ║${NC}"
    echo -e "${BLUE}║                   Linux / CUPS                     ║${NC}"
    echo -e "${BLUE}║                                                    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo -e "${RED}❌ Este script debe ejecutarse como root (sudo)${NC}"
        echo ""
        echo "Uso correcto:"
        echo "  sudo $0 [IP_SERVIDOR] [PUERTO]"
        echo ""
        exit 1
    fi
}

check_cups() {
    echo -e "${BLUE}🔍 Verificando instalación de CUPS...${NC}"
    
    if ! command -v lpstat &> /dev/null; then
        echo -e "${RED}❌ CUPS no está instalado${NC}"
        echo ""
        echo "Para instalar CUPS:"
        echo ""
        echo "  Ubuntu/Debian:"
        echo "    sudo apt-get update"
        echo "    sudo apt-get install cups"
        echo ""
        echo "  Fedora/RHEL:"
        echo "    sudo dnf install cups"
        echo ""
        echo "  Arch Linux:"
        echo "    sudo pacman -S cups"
        echo ""
        exit 1
    fi
    
    # Verificar que CUPS esté corriendo
    if ! systemctl is-active --quiet cups 2>/dev/null; then
        echo -e "${YELLOW}⚠️  CUPS no está corriendo. Iniciando...${NC}"
        systemctl start cups
        sleep 2
    fi
    
    echo -e "${GREEN}✅ CUPS está instalado y corriendo${NC}"
}

find_ppd_file() {
    echo -e "${BLUE}🔍 Buscando archivo PPD...${NC}"
    
    # Buscar PPD en varias ubicaciones
    PPD_LOCATIONS=(
        "$(dirname "$0")/../ppd/${PPD_FILE}"
        "$(dirname "$0")/${PPD_FILE}"
        "/tmp/${PPD_FILE}"
        "${PPD_FILE}"
    )
    
    for location in "${PPD_LOCATIONS[@]}"; do
        if [ -f "$location" ]; then
            PPD_PATH="$location"
            echo -e "${GREEN}✅ PPD encontrado: ${PPD_PATH}${NC}"
            return 0
        fi
    done
    
    echo -e "${RED}❌ No se encontró el archivo PPD: ${PPD_FILE}${NC}"
    echo ""
    echo "Asegúrate de que el archivo ${PPD_FILE} esté en:"
    echo "  - $(dirname "$0")/../ppd/"
    echo "  - $(dirname "$0")/"
    echo ""
    exit 1
}

remove_existing_printer() {
    echo -e "${BLUE}🔍 Verificando si la impresora ya existe...${NC}"
    
    if lpstat -p "${PRINTER_NAME}" &> /dev/null; then
        echo -e "${YELLOW}⚠️  La impresora '${PRINTER_NAME}' ya existe. Eliminando...${NC}"
        lpadmin -x "${PRINTER_NAME}"
        echo -e "${GREEN}✅ Impresora anterior eliminada${NC}"
    else
        echo -e "${GREEN}✅ No hay conflictos${NC}"
    fi
}

install_printer() {
    echo -e "${BLUE}📥 Instalando impresora...${NC}"
    echo ""
    echo "  Nombre: ${PRINTER_NAME}"
    echo "  URI: ${PRINTER_URI}"
    echo "  Descripción: ${PRINTER_DESCRIPTION}"
    echo "  Ubicación: ${PRINTER_LOCATION}"
    echo ""
    
    # Instalar impresora con lpadmin
    lpadmin -p "${PRINTER_NAME}" \
        -v "${PRINTER_URI}" \
        -P "${PPD_PATH}" \
        -D "${PRINTER_DESCRIPTION}" \
        -L "${PRINTER_LOCATION}" \
        -E \
        -o printer-is-shared=false \
        -o printer-error-policy=retry-job
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error al instalar la impresora${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Impresora instalada correctamente${NC}"
}

enable_printer() {
    echo -e "${BLUE}🔌 Habilitando impresora...${NC}"
    
    # Habilitar impresora
    cupsenable "${PRINTER_NAME}"
    
    # Aceptar trabajos
    cupsaccept "${PRINTER_NAME}"
    
    echo -e "${GREEN}✅ Impresora habilitada y lista para imprimir${NC}"
}

set_default_printer() {
    echo ""
    echo -e "${YELLOW}¿Deseas establecer ONE-POS como impresora predeterminada? (s/n)${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Ss]$ ]]; then
        lpadmin -d "${PRINTER_NAME}"
        echo -e "${GREEN}✅ ONE-POS establecida como impresora predeterminada${NC}"
    else
        echo -e "${BLUE}ℹ️  Impresora instalada pero no como predeterminada${NC}"
    fi
}

test_printer() {
    echo ""
    echo -e "${YELLOW}¿Deseas imprimir una página de prueba? (s/n)${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Ss]$ ]]; then
        echo -e "${BLUE}🖨️  Imprimiendo página de prueba...${NC}"
        
        # Crear página de prueba simple
        echo "╔════════════════════════════════╗
║  ONE-POS Network Printer       ║
║  Página de Prueba              ║
╠════════════════════════════════╣
║                                ║
║  ✓ Instalación exitosa         ║
║  ✓ Conexión establecida        ║
║  ✓ Lista para imprimir         ║
║                                ║
║  Fecha: $(date '+%Y-%m-%d %H:%M')   ║
║                                ║
╚════════════════════════════════╝" | lp -d "${PRINTER_NAME}"
        
        echo -e "${GREEN}✅ Página de prueba enviada${NC}"
    fi
}

show_success_info() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                    ║${NC}"
    echo -e "${GREEN}║        ✅ INSTALACIÓN COMPLETADA EXITOSAMENTE       ║${NC}"
    echo -e "${GREEN}║                                                    ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}📋 Información de la impresora:${NC}"
    echo ""
    echo "  Nombre: ${PRINTER_NAME}"
    echo "  URI: ${PRINTER_URI}"
    echo "  Estado: $(lpstat -p "${PRINTER_NAME}" 2>/dev/null | awk '{print $3}')"
    echo ""
    echo -e "${BLUE}🔧 Comandos útiles:${NC}"
    echo ""
    echo "  Ver estado:     lpstat -p ${PRINTER_NAME}"
    echo "  Ver trabajos:   lpq -P ${PRINTER_NAME}"
    echo "  Imprimir:       lp -d ${PRINTER_NAME} archivo.pdf"
    echo "  Eliminar:       sudo lpadmin -x ${PRINTER_NAME}"
    echo ""
    echo -e "${BLUE}🌐 Interfaz web de CUPS:${NC}"
    echo ""
    echo "  http://localhost:631"
    echo ""
}

################################################################################
# Script principal
################################################################################

main() {
    print_banner
    
    echo -e "${BLUE}📦 Parámetros de instalación:${NC}"
    echo "  Servidor: ${SERVER_IP}"
    echo "  Puerto: ${SERVER_PORT}"
    echo ""
    
    check_root
    check_cups
    find_ppd_file
    remove_existing_printer
    install_printer
    enable_printer
    set_default_printer
    test_printer
    show_success_info
}

# Ejecutar script
main "$@"
