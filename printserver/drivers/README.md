# 🖨️ ONE-POS Network Printer - Instaladores de Drivers

Este directorio contiene los **instaladores rápidos** para conectar tu computadora a la impresora ONE-POS Network Printer.

---

## 📥 Instalación Rápida

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch, etc.)

```bash
# 1. Descargar el instalador
wget https://github.com/tu-repo/drivers/install-linux.sh

# 2. Dar permisos de ejecución
chmod +x install-linux.sh

# 3. Ejecutar (con la IP de tu servidor)
sudo ./install-linux.sh 192.168.1.100 631

# O si el servidor está en la misma máquina:
sudo ./install-linux.sh
```

**¡Listo!** La impresora está instalada y lista para usar.

---

### 🪟 Windows (10/11)

#### Opción 1: Script .BAT (Simple)

1. **Descargar** `install-windows.bat`
2. **Hacer clic derecho** → **"Ejecutar como administrador"**
3. **Seguir las instrucciones** en pantalla

#### Opción 2: Script PowerShell (Avanzado)

```powershell
# 1. Abrir PowerShell como Administrador
# 2. Permitir ejecución de scripts (solo primera vez)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. Ejecutar instalador
.\install-windows.ps1 -ServerIP "192.168.1.100" -ServerPort 631

# O con valores por defecto (localhost):
.\install-windows.ps1
```

**¡Listo!** La impresora está instalada y lista para usar.

---

## 📋 Requisitos

### Linux
- ✅ CUPS instalado (`sudo apt install cups` en Ubuntu/Debian)
- ✅ Permisos de administrador (sudo)
- ✅ Conexión de red al servidor IPP

### Windows
- ✅ Windows 10 o superior
- ✅ Permisos de administrador
- ✅ Conexión de red al servidor IPP

---

## 🎯 Parámetros de Instalación

Ambos scripts aceptan los mismos parámetros:

| Parámetro | Descripción | Por defecto |
|-----------|-------------|-------------|
| **IP del Servidor** | Dirección IP donde corre el servidor IPP | `localhost` |
| **Puerto** | Puerto del servidor IPP | `631` |

### Ejemplos:

```bash
# Servidor en la misma máquina
sudo ./install-linux.sh

# Servidor en otra máquina de la red
sudo ./install-linux.sh 192.168.1.100 631

# Servidor con puerto personalizado
sudo ./install-linux.sh 10.0.0.50 8631
```

---

## 🔧 Verificación Post-Instalación

### Linux

```bash
# Ver estado de la impresora
lpstat -p ONE-POS-Printer

# Ver trabajos de impresión
lpq -P ONE-POS-Printer

# Imprimir archivo de prueba
lp -d ONE-POS-Printer documento.pdf

# Abrir interfaz web de CUPS
xdg-open http://localhost:631
```

### Windows

1. Abrir **Panel de Control** → **Dispositivos e Impresoras**
2. Buscar **"ONE-POS-Printer"**
3. Hacer clic derecho → **"Propiedades de impresora"**
4. Clic en **"Imprimir página de prueba"**

---

## ❌ Desinstalación

### Linux

```bash
# Eliminar impresora
sudo lpadmin -x ONE-POS-Printer

# Verificar eliminación
lpstat -p ONE-POS-Printer
```

### Windows PowerShell

```powershell
# Eliminar impresora
Remove-Printer -Name "ONE-POS-Printer" -Confirm:$false

# Verificar eliminación
Get-Printer -Name "ONE-POS-Printer"
```

---

## 🐛 Solución de Problemas

### ❌ Error: "CUPS no está instalado" (Linux)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install cups

# Fedora/RHEL
sudo dnf install cups

# Arch Linux
sudo pacman -S cups

# Iniciar servicio
sudo systemctl start cups
sudo systemctl enable cups
```

### ❌ Error: "No se pudo conectar a la impresora"

1. **Verificar que el servidor IPP esté corriendo**
   ```bash
   curl http://IP_SERVIDOR:631/ipp/printer
   ```

2. **Verificar firewall**
   ```bash
   # Linux
   sudo ufw allow 631/tcp
   
   # Windows (ejecutar como admin)
   netsh advfirewall firewall add rule name="IPP Printer" dir=in action=allow protocol=TCP localport=631
   ```

3. **Verificar conectividad de red**
   ```bash
   ping IP_SERVIDOR
   ```

### ❌ Error: "Archivo PPD no encontrado" (Linux)

El instalador de Linux busca el PPD en estas ubicaciones:
- `../ppd/ONEPOS-IPP.ppd` (relativo al script)
- `./ONEPOS-IPP.ppd` (mismo directorio)
- `/tmp/ONEPOS-IPP.ppd`

**Solución:**
```bash
# Copiar PPD al directorio del script
cp /ruta/al/ONEPOS-IPP.ppd .

# O ejecutar desde la carpeta correcta
cd /ruta/al/printserver/drivers
sudo ./install-linux.sh
```

### ❌ Error: "Debe ejecutarse como Administrador" (Windows)

**Solución:**
1. Hacer clic derecho en `install-windows.bat` o `install-windows.ps1`
2. Seleccionar **"Ejecutar como administrador"**
3. Aceptar el diálogo de UAC (Control de Cuentas de Usuario)

---

## 📁 Estructura de Archivos

```
printserver/
├── drivers/
│   ├── install-linux.sh          # Instalador para Linux
│   ├── install-windows.bat       # Instalador para Windows (simple)
│   ├── install-windows.ps1       # Instalador para Windows (avanzado)
│   └── README.md                 # Esta guía
├── ppd/
│   └── ONEPOS-IPP.ppd           # Archivo PPD (PostScript Printer Description)
└── ...
```

---

## 🎓 ¿Qué hace cada instalador?

### Linux (`install-linux.sh`)
1. ✅ Verifica que CUPS esté instalado
2. ✅ Busca el archivo PPD automáticamente
3. ✅ Elimina instalaciones previas (si existen)
4. ✅ Crea la impresora en CUPS con el PPD correcto
5. ✅ Habilita la impresora
6. ✅ Opcionalmente la establece como predeterminada
7. ✅ Opcionalmente imprime página de prueba

### Windows (`install-windows.bat` / `.ps1`)
1. ✅ Verifica permisos de administrador
2. ✅ Elimina instalaciones previas (si existen)
3. ✅ Crea puerto IPP
4. ✅ Instala impresora con driver IPP de Microsoft
5. ✅ Opcionalmente la establece como predeterminada
6. ✅ Opcionalmente imprime página de prueba

---

## 🔐 Seguridad

Los scripts:
- ✅ Requieren permisos de administrador explícitamente
- ✅ Solo modifican configuración de impresoras
- ✅ No descargan ni ejecutan código remoto
- ✅ Son open source y auditables
- ✅ No recopilan ni envían información

---

## 🆘 Soporte

### Instalación Manual

Si los scripts automáticos no funcionan, puedes instalar manualmente:

#### Linux (Manual)
```bash
# 1. Copiar PPD a directorio de CUPS
sudo cp ONEPOS-IPP.ppd /usr/share/cups/model/

# 2. Agregar impresora
sudo lpadmin -p ONE-POS-Printer \
    -v ipp://IP_SERVIDOR:631/ipp/printer \
    -P /usr/share/cups/model/ONEPOS-IPP.ppd \
    -D "ONE POS Network Printer" \
    -L "Office" \
    -E

# 3. Habilitar
sudo cupsenable ONE-POS-Printer
sudo cupsaccept ONE-POS-Printer
```

#### Windows (Manual)
1. Abrir **Panel de Control** → **Dispositivos e Impresoras**
2. Clic en **"Agregar una impresora"**
3. Seleccionar **"La impresora que deseo no está en la lista"**
4. Seleccionar **"Agregar una impresora mediante dirección TCP/IP"**
5. Tipo: **IPP**
6. URL: `http://IP_SERVIDOR:631/ipp/printer`
7. Nombre: `ONE-POS-Printer`
8. Usar driver: **Microsoft IPP Class Driver** o **Generic / Text Only**

---

## 📞 Contacto

Si tienes problemas o sugerencias:
- 📧 Email: soporte@tu-empresa.com
- 🐛 Issues: https://github.com/tu-repo/issues
- 📖 Docs: https://docs.tu-empresa.com

---

## 📄 Licencia

MIT License - Ver archivo LICENSE para detalles

---

**Versión:** 1.0.0  
**Última actualización:** 28 de noviembre de 2025
