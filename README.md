# 🖨️ Servidor de Impresión ESC/POS para Impresora Térmica Q-Cube

Sistema de impresión sencillo y confiable para impresoras térmicas. Permite imprimir documentos PDF e imágenes desde cualquier navegador web, sin necesidad de instalar drivers complicados.

---

## 📥 Descarga

Descarga la última versión desde GitHub Releases:

**📦 [Descargar Servidor de Impresión v1.0.0](https://github.com/I-Labs-Chile/ONE-POS-Utilidades/releases/download/1.0.0/escpos-server-linux-x64-v1.0.0.tar.gz)**

> Archivo: `escpos-server-linux-x64-v1.0.0.tar.gz` (~33 MB)

---

## 🚀 Instalación y Primer Uso

### Paso 1: Instalar Dependencias del Sistema

Abre una terminal y ejecuta:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils libusb-1.0-0
```

> **¿Qué hace esto?** Instala las herramientas necesarias para procesar archivos PDF e impresoras USB.

### Paso 2: Extraer el Archivo

1. Ve a la carpeta donde descargaste el archivo (normalmente **Descargas**)
2. **Click derecho** en `escpos-server-linux-x64-v1.0.0.tar.gz`
3. Selecciona **"Extraer aquí"**
4. Se creará una carpeta llamada `escpos-server-linux-x64-v1.0.0`

### Paso 3: Abrir Terminal en la Carpeta

1. Abre la carpeta `escpos-server-linux-x64-v1.0.0`
2. **Click derecho** dentro de la carpeta (en un espacio vacío)
3. Selecciona **"Abrir en terminal"** o **"Open in Terminal"**

### Paso 4: Iniciar el Servidor

En la terminal que se abrió, ejecuta:

```bash
sudo ./launch-server.sh
```

> **Nota:** Se te pedirá tu contraseña de administrador (sudo).

### ✅ ¿Cómo sé que está funcionando?

Si todo salió bien, se abrirá una **nueva ventana de terminal** mostrando algo como esto:

```
╔═══════════════════════════════════════════════╗
║  Servidor de Impresión ESC/POS - Q-Cube      ║
║  Logs en tiempo real                          ║
╚═══════════════════════════════════════════════╝

Iniciando servidor...

============================================================
    SERVIDOR DE IMPRESIÓN ESC/POS - Q-CUBE
============================================================
  Host: 0.0.0.0
  Puerto: 8080
  Acceso local: http://localhost:8080
  Presiona Ctrl+C para detener el servidor
============================================================

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
# Worker de impresión iniciado
Impresora conectada: /dev/usb/lp0
```

> 🎉 **¡Listo!** El servidor está corriendo correctamente.

---

## 🌐 Usar la Interfaz Web

### Desde el Mismo Computador

1. Abre tu navegador web (Chrome, Firefox, etc.)
2. Ve a: **http://localhost:8080**
3. Verás la interfaz de impresión

### Imprimir un Documento

1. **Arrastra** un archivo PDF o imagen al cuadro de impresión
2. O haz **click** en el cuadro para seleccionar un archivo
3. El documento se enviará automáticamente a la impresora

**Formatos soportados:**
- 📄 PDF
- 🖼️ Imágenes: JPG, PNG, BMP, GIF, WEBP

### 🛑 Detener el Servidor

Para detener el servidor:
- **Cierra la ventana** de la terminal que se abrió
- O presiona `Ctrl+C` en la terminal

---

## 📱 Imprimir desde Otros Dispositivos

### Desde un Celular o Tablet

1. Asegúrate de que el celular/tablet esté **conectado a la misma red WiFi** que el computador
2. En el celular, abre el navegador (Chrome, Safari, etc.)
3. Averigua la IP del computador donde corre el servidor:
   - En la terminal del servidor, busca una línea que dice algo como:
   ```
   Impresora conectada: /dev/usb/lp0
   ```
   - O ejecuta en otra terminal: `ip addr show | grep inet`
4. En el celular, ve a: `http://IP-DEL-COMPUTADOR:8080`
   - Por ejemplo: `http://192.168.1.100:8080`
5. ¡Ya puedes arrastrar archivos desde tu celular!

### Desde Otra Computadora

1. Conecta la otra computadora a la **misma red**
2. Abre el navegador
3. Ve a: `http://IP-DEL-SERVIDOR:8080`

---

## ⚙️ Configuración Avanzada (Opcional)

### Cambiar el Puerto del Servidor

Si el puerto 8080 está ocupado o quieres usar otro:

1. En la carpeta del servidor, copia el archivo de ejemplo:
   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env`:
   ```bash
   nano .env
   ```

3. Cambia la línea:
   ```
   SERVER_PORT=8080
   ```
   Por el puerto que quieras, por ejemplo:
   ```
   SERVER_PORT=3000
   ```

4. Guarda y reinicia el servidor

### Usar Impresora de Red (TCP/IP)

Si tu impresora se conecta por red en lugar de USB:

1. Edita el archivo `.env`:
   ```bash
   nano .env
   ```

2. Cambia estas líneas:
   ```
   PRINTER_IF=tcp
   PRINTER_HOST=192.168.1.100  # IP de tu impresora
   PRINTER_PORT=9100            # Puerto de la impresora
   ```

3. Guarda y reinicia el servidor

### Papel de 80mm en lugar de 58mm

1. Edita el archivo `.env`:
   ```bash
   nano .env
   ```

2. Cambia:
   ```
   PAPER_WIDTH_PX=576  # Para papel de 80mm
   ```

3. Guarda y reinicia el servidor

---

## 🆘 Solución de Problemas

### ❌ "No se encuentra la impresora"

**Solución:**
1. Verifica que la impresora esté conectada y encendida
2. Ejecuta: `lsusb` para ver si aparece la impresora
3. Asegúrate de haber reiniciado sesión después de agregar tu usuario al grupo `lp`
4. Si aún no funciona, ejecuta el servidor con `sudo`:
   ```bash
   sudo ./launch-server.sh
   ```

### ❌ "Permission denied en /dev/usb/lp0"

**Solución:**
```bash
# Agregar tu usuario al grupo lp
sudo usermod -a -G lp $USER

# Cerrar sesión completamente y volver a entrar
# O ejecutar con sudo
sudo ./launch-server.sh
```

### ❌ "Puerto 8080 en uso"

**Solución 1 - Cambiar el puerto:**
1. Edita `.env` y cambia `SERVER_PORT=8080` por otro puerto (ej: `SERVER_PORT=3000`)
2. Reinicia el servidor

**Solución 2 - Cerrar el programa que usa el puerto:**
```bash
# Ver qué programa usa el puerto 8080
sudo lsof -ti:8080

# Cerrar ese programa
sudo kill $(sudo lsof -ti:8080)
```

### ❌ "No puedo acceder desde otro dispositivo"

**Solución:**
1. Verifica que ambos dispositivos estén en la misma red WiFi
2. Desactiva el firewall temporalmente o permite el puerto 8080:
   ```bash
   sudo ufw allow 8080
   ```
3. Usa la IP correcta (no uses `localhost` desde otro dispositivo)

### ❌ "Los documentos salen muy claros o muy oscuros"

El servidor ajusta automáticamente el brillo y contraste, pero si aún no se ve bien:

1. Revisa la configuración de densidad de tu impresora
2. Limpia el cabezal de la impresora
3. Verifica que estés usando papel térmico de buena calidad

### ❌ "La impresión sale cortada"

**Solución:**
Cambia el ancho del papel según tu impresora:
- Para papel de **58mm**: `PAPER_WIDTH_PX=384` (predeterminado)
- Para papel de **80mm**: `PAPER_WIDTH_PX=576`

---

## 📞 Soporte

Si tienes problemas o preguntas:

- **GitHub Issues**: [https://github.com/I-Labs-Chile/ONE-POS-Utilidades/issues](https://github.com/I-Labs-Chile/ONE-POS-Utilidades/issues)
- **Email**: soporte@i-labs.cl

---

## 📄 Información Técnica (Para Desarrolladores)

### 🖨️ Impresión Avanzada
- **PDF → Raster → Monocromo**: Conversión automática con dithering de alta calidad
- **Imágenes directas**: Soporta JPG, PNG, BMP, GIF, WEBP
- **Normalización automática**: Mejora la calidad de imágenes oscuras o de bajo contraste
- **Cola persistente**: Gestión secuencial de trabajos con recuperación ante fallos
- **Impresión de bienvenida**: Ticket automático con QR al iniciar el servidor

### 🔧 Algoritmos de Normalización de Imagen

#### 1. **Normalización Automática de Brillo**
- Detecta y corrige imágenes muy oscuras (brillo < 100)
- Ajusta imágenes muy claras (brillo > 180)
- Aumenta contraste automáticamente en un 30%

#### 2. **Ajuste Automático de Niveles**
- Expande el histograma al rango completo [0-255]
- Usa percentiles (2% y 98%) para ignorar outliers
- Mejora el rango dinámico sin saturación

#### 3. **Dithering Floyd-Steinberg**
- Algoritmo de difusión de error de alta calidad
- Produce gradientes suaves en lugar de bloques sólidos
- Resultado superior al dithering por defecto de PIL

### 🌐 API HTTP Completa

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Interfaz web para subir archivos |
| `/imprimir` | POST | Subir PDF y encolar impresión |
| `/imprimir-imagen` | POST | Subir imagen (JPG, PNG, etc.) y encolar |
| `/cola` | GET | Estado de la cola (pendientes e impresos) |
| `/salud` | GET | Healthcheck con métricas (cola, IP, impresora) |
| `/estado` | GET | IP local y configuración detallada de impresora |
| `/test-impresora` | POST | Ejecutar impresión de prueba manualmente |

#### Respuesta de `/salud`
```json
{
  "ok": true,
  "cola_pendientes": 0,
  "ultimos_impresos": 10,
  "ip_local": "192.168.100.25",
  "impresora": {
    "interfaz": "usb",
    "usb_vendor": 0,
    "usb_product": 0,
    "paper_width_px": 384
  }
}
```

### 💡 Funcionalidades Destacadas

- ✅ **Sin dependencias del sistema**: No requiere CUPS, IPP ni drivers
- ✅ **Bajo consumo de recursos**: Ideal para Raspberry Pi Zero
- ✅ **Empaquetable**: Genera binario único con PyInstaller
- ✅ **Interfaz web moderna**: HTML5 con drag & drop y paste
- ✅ **Healthcheck automático**: Monitoreo del estado cada 5 segundos
- ✅ **Códigos QR**: Generación automática con tamaño ajustable
- ✅ **Logs en español**: Diagnóstico orientado a campo
- ✅ **Recuperación ante fallos**: Cola persistente en JSON

## Requisitos

### Sistema Operativo
- Linux (probado en Ubuntu/Debian y Raspberry Pi OS)
- Python 3.9+ (recomendado 3.11+)

### Dependencias del Sistema
```bash
sudo apt-get update
sudo apt-get install -y poppler-utils libusb-1.0-0
```

### Dependencias de Python
- **FastAPI**: Servidor HTTP moderno y rápido
- **Uvicorn**: Servidor ASGI de alto rendimiento
- **Pillow**: Procesamiento de imágenes (resize, grayscale, dithering)
- **NumPy**: Algoritmos de normalización y procesamiento matricial
- **PyUSB**: Comunicación USB con impresoras (opcional, usa fallback a `/dev/usb/lp*`)
- **Pydantic**: Validación de datos y configuración
- **Python-multipart**: Manejo de uploads de archivos

## Instalación

### Instalación Rápida
```bash
# 1. Instalar dependencias del sistema
sudo apt-get update && sudo apt-get install -y poppler-utils libusb-1.0-0

# 2. Crear entorno virtual
python3 -m venv .venv && source .venv/bin/activate

# 3. Instalar dependencias de Python
pip install -r requirements.txt

# 4. Configurar permisos USB (si usas USB)
sudo usermod -a -G lp $USER
# Cerrar sesión y volver a entrar para aplicar cambios
```

## Ejecución

### Desarrollo
```bash
# Activar entorno virtual
source .venv/bin/activate

# Ejecutar servidor
python run.py

# O directamente con uvicorn
uvicorn app.web.api:app --host 0.0.0.0 --port 8080 --reload
```

### Producción
```bash
# Con systemd (ver sección de servicio más abajo)
sudo systemctl start escpos-server

# O manualmente en background
nohup .venv/bin/python run.py > server.log 2>&1 &
```

Al iniciar, el servidor **imprimirá automáticamente** un ticket de bienvenida con un código QR para acceder a la interfaz web.

## Variables de Entorno

### Configuración de Impresora
| Variable | Descripción | Valores | Por Defecto |
|----------|-------------|---------|-------------|
| `PRINTER_IF` | Interfaz de comunicación | `tcp`, `usb` | `usb` |
| `PRINTER_HOST` | IP/host para impresoras TCP | Cualquier IP | `127.0.0.1` |
| `PRINTER_PORT` | Puerto TCP | 1-65535 | `9100` |
| `USB_VENDOR` | Vendor ID USB (hex o decimal) | Ej: `0x04b8` | `0` (autodetección) |
| `USB_PRODUCT` | Product ID USB (hex o decimal) | Ej: `0x0202` | `0` (autodetección) |

### Configuración de Papel
| Variable | Descripción | Valores | Por Defecto |
|----------|-------------|---------|-------------|
| `PAPER_WIDTH_PX` | Ancho del papel en píxeles | 384 (58mm), 576 (80mm) | `384` |
| `RASTER_DPI` | DPI para rasterizar PDFs | 203, 300 | `203` |

### Configuración de Cola
| Variable | Descripción | Por Defecto |
|----------|-------------|-------------|
| `QUEUE_DIR` | Directorio para cola y trabajos | `./data` |
| `SERVER_PORT` | Puerto del servidor HTTP | `8080` |

### Ejemplo de Configuración
```bash
# Impresora USB con autodetección
export PRINTER_IF=usb
export PAPER_WIDTH_PX=384

# Impresora de red TCP
export PRINTER_IF=tcp
export PRINTER_HOST=192.168.1.100
export PRINTER_PORT=9100
export PAPER_WIDTH_PX=576

# Impresora USB específica
export PRINTER_IF=usb
export USB_VENDOR=0x04b8
export USB_PRODUCT=0x0202
```

## Flujo de Impresión

### 1. Subida de Archivo
El cliente sube un PDF o imagen vía POST `/imprimir` o `/imprimir-imagen`

### 2. Encolado
Se crea un trabajo con metadatos:
- ID único (UUID)
- IP del cliente
- Nombre original del archivo
- Timestamp
- Estado inicial: `PENDING`

### 3. Procesamiento (Worker)

#### Para PDFs:
1. **Rasterización**: `pdftoppm` convierte cada página a PNG
2. **Normalización**: Ajuste automático de brillo y niveles
3. **Conversión a monocromo**: Dithering Floyd-Steinberg
4. **Generación ESC/POS**: Comandos raster para cada página
5. **Envío**: Transmisión por USB o TCP

#### Para Imágenes:
1. **Carga directa**: PIL abre la imagen
2. **Normalización**: Algoritmos de mejora de calidad
3. **Redimensionado**: Ajuste al ancho del papel
4. **Conversión a monocromo**: Dithering de alta calidad
5. **Generación ESC/POS**: Comandos raster
6. **Envío**: Transmisión por USB o TCP

### 4. Actualización de Estado
- `PROCESSING`: Durante la impresión
- `PRINTED`: Completado exitosamente
- `ERROR`: Fallo (con mensaje de error)

## Cola y Persistencia

### Gestión de Trabajos
- **Trabajos pendientes**: Se mantienen hasta completarse
- **Trabajos impresos**: Cache de últimos 10
- **Limpieza automática**: Trabajos antiguos se eliminan del cache
- **Persistencia**: Estado guardado en `./data/queue.json`
- **Archivos temporales**: `./data/jobs/` (se limpian al completar)

## Servicio Systemd

### Instalación del Servicio

1. **Editar el archivo de servicio**
```bash
nano deploy/escpos-server.service
```

Ajusta las rutas y usuario:
```ini
[Unit]
Description=ONE-POS ESC/POS Print Server
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/a/ONE-POS-Utilidades
ExecStart=/ruta/a/ONE-POS-Utilidades/.venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. **Copiar y habilitar**
```bash
sudo cp deploy/escpos-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable escpos-server
sudo systemctl start escpos-server
```

3. **Verificar estado**
```bash
sudo systemctl status escpos-server
sudo journalctl -u escpos-server -f
```

## Empaquetar como Binario Único

### Con PyInstaller
```bash
# Instalar PyInstaller
pip install pyinstaller

# Generar binario
pyinstaller --onefile --name escpos-server \
  --add-data "app/web/frontend:app/web/frontend" \
  run.py

# El binario estará en dist/escpos-server
./dist/escpos-server
```

### Notas sobre Empaquetado
- Los archivos estáticos del frontend se incluyen automáticamente
- El binario incluye todas las dependencias de Python
- **No incluye**: `poppler-utils` ni `libusb` (deben instalarse en el sistema destino)
- Tamaño aproximado: 15-25 MB

## Diagnóstico y Solución de Problemas

### Verificar Conectividad

#### Healthcheck
```bash
curl http://localhost:8080/salud | jq
```

#### Estado del Sistema
```bash
curl http://localhost:8080/estado | jq
```

### Problemas Comunes

#### USB sin PyUSB
**Síntoma**: No se detecta la impresora
**Solución**:
1. Verificar que exista `/dev/usb/lp0` o similar
2. Dar permisos: `sudo usermod -a -G lp $USER`
3. Reiniciar sesión

#### PyUSB: Dispositivo no encontrado
**Síntoma**: Error "No se pudo inicializar la impresora USB"
**Solución**:
1. Instalar libusb: `sudo apt-get install libusb-1.0-0`
2. Buscar vendor/product ID: `lsusb`
3. Exportar variables:
```bash
export USB_VENDOR=0x04b8
export USB_PRODUCT=0x0202
```

#### Rasterización de PDF falla
**Síntoma**: Error al procesar PDFs
**Solución**:
1. Verificar poppler: `pdftoppm -v`
2. Instalar si falta: `sudo apt-get install poppler-utils`

#### Ancho de papel incorrecto
**Síntoma**: Imagen cortada o muy pequeña
**Solución**:
```bash
# Para papel de 58mm
export PAPER_WIDTH_PX=384

# Para papel de 80mm
export PAPER_WIDTH_PX=576
```

#### Impresión muy oscura
**Síntoma**: Imágenes salen completamente negras
**Solución**: El sistema aplica normalización automática. Si persiste:
1. Verificar que numpy esté instalado
2. Revisar logs del worker
3. Usar el script de prueba: `python test_image_quality.py imagen.jpg`

## Estructura del Proyecto

```
ONE-POS-Utilidades/
├── app/
│   ├── core/
│   │   ├── queue.py          # Cola persistente de trabajos
│   │   ├── worker.py         # Worker de impresión secuencial
│   │   └── test_print.py     # Impresión de prueba y bienvenida
│   ├── utils/
│   │   ├── escpos.py         # Envío de comandos ESC/POS (TCP/USB)
│   │   ├── image.py          # Procesamiento y normalización de imágenes
│   │   ├── network.py        # Utilidades de red (IP local)
│   │   ├── usb_detector.py   # Detección de impresoras USB
│   │   └── usb_printer.py    # Backend USB especializado
│   └── web/
│       ├── api.py            # API FastAPI con todos los endpoints
│       ├── frontend.py       # Entrega de interfaz web estática
│       └── frontend/
│           ├── index.html    # Interfaz de usuario HTML5
│           └── src/
│               ├── app.js    # Lógica JavaScript (upload, healthcheck)
│               ├── styles.css # Estilos CSS
│               └── empresa.png # Logo/imagen de la empresa
├── data/
│   ├── queue.json           # Estado persistente de la cola
│   └── jobs/                # Archivos temporales de trabajos
├── deploy/
│   └── escpos-server.service # Servicio systemd
├── run.py                   # Punto de entrada principal
├── requirements.txt         # Dependencias de Python
├── test_image_quality.py    # Script de prueba de calidad de imagen
└── README.md               # Este archivo
```

## Arquitectura y Componentes

### Módulo Core

#### `queue.py` - Gestión de Cola
- **PrintQueue**: Cola persistente con operaciones thread-safe
- **PrintJob**: Modelo de trabajo con estados (PENDING, PROCESSING, PRINTED, ERROR)
- **JobState**: Enum de estados posibles
- Serialización/deserialización JSON automática
- Cache de últimos 10 trabajos impresos

#### `worker.py` - Worker de Impresión
- Hilo daemon que procesa la cola secuencialmente
- Rasterización de PDFs con `pdftoppm`
- Procesamiento de imágenes con normalización
- Gestión de conexión con impresora (TCP/USB)
- Manejo de errores y actualización de estados
- **Impresión automática de bienvenida** al iniciar

#### `test_print.py` - Impresión de Prueba
- Ticket de bienvenida con información del servidor
- Código QR de tamaño completo (16x16) con URL de acceso
- Validación de conectividad con la impresora
- Endpoint manual `/test-impresora`

### Módulo Utils

#### `escpos.py` - Comandos ESC/POS
- **EscposSender**: Clase principal de comunicación
- Soporte TCP (raw socket) y USB (PyUSB/libusb + fallback a `/dev/usb/lp*`)
- Comandos implementados:
  - `init()`: Inicialización de impresora
  - `text()`: Impresión de texto
  - `print_qr()`: Generación de códigos QR (tamaño ajustable 1-16)
  - `print_image()`: Impresión de imágenes raster
  - `cut()`: Corte de papel
  - `feed()`: Avance de líneas

#### `image.py` - Procesamiento de Imágenes
Funciones de normalización:
- **`_normalize_brightness()`**: Ajuste automático de brillo según luminosidad promedio
- **`_auto_levels()`**: Expansión de histograma usando percentiles
- **`_floyd_steinberg_dithering()`**: Dithering de alta calidad con difusión de error
- **`to_thermal_mono_dither()`**: Función principal de conversión a monocromo

Algoritmos aplicados:
1. Resize proporcional al ancho del papel
2. Conversión a escala de grises
3. Normalización de brillo (corrige oscuridad/claridad extrema)
4. Ajuste automático de niveles (expande rango dinámico)
5. Dithering Floyd-Steinberg (gradientes suaves)
6. Conversión final a 1-bit (blanco/negro puro)

#### `network.py` - Utilidades de Red
- `get_primary_ip()`: Obtiene la IP local principal
- Usado para construir URLs en códigos QR

#### `usb_detector.py` & `usb_printer.py`
- Detección automática de impresoras USB
- Backend especializado para comunicación USB
- Fallback a múltiples métodos (PyUSB, archivo de dispositivo)

### Módulo Web

#### `api.py` - API REST
Endpoints implementados:
- **GET `/`**: Interfaz web
- **POST `/imprimir`**: Upload de PDF
- **POST `/imprimir-imagen`**: Upload de imagen
- **GET `/cola`**: Estado de cola
- **GET `/salud`**: Healthcheck
- **GET `/estado`**: Configuración del sistema
- **POST `/test-impresora`**: Prueba manual

#### `frontend.py` - Servidor de Frontend
- Carga del HTML estático desde disco
- Soporte para empaquetado con PyInstaller (`_MEIPASS`)
- Fallback a mensaje de error si no se encuentra el frontend

#### Frontend (HTML/CSS/JS)
- **HTML5**: Estructura semántica con drag & drop
- **CSS3**: Diseño responsive y moderno
- **JavaScript**: 
  - Upload de archivos (click, drag, paste)
  - Healthcheck automático cada 5 segundos
  - Indicador visual de estado (verde/amarillo/rojo)
  - Manejo de errores con feedback visual

## Testing y Desarrollo

### Probar Calidad de Impresión
```bash
# Comparar procesamiento con/sin mejoras
.venv/bin/python test_image_quality.py foto_oscura.jpg

# Genera:
# - test_sin_mejoras.png (método antiguo)
# - test_con_mejoras.png (con normalización)
```

### Probar Impresora Manualmente
```bash
# Via API
curl -X POST http://localhost:8080/test-impresora
```

### Monitorear Logs en Tiempo Real
```bash
# Desarrollo
.venv/bin/python run.py

# Producción (systemd)
sudo journalctl -u escpos-server -f
```

## Notas Técnicas

### Sin Dependencias del Sistema de Impresión
- **No usa CUPS**: Comunicación directa con hardware
- **No usa IPP**: Protocolo propietario ESC/POS
- **No requiere drivers**: Comandos raw ESC/POS universales

### Optimizaciones de Rendimiento
- Worker en hilo daemon (no bloquea la API)
- Cola persistente (recupera trabajos tras reinicio)
- Cache de trabajos impresos (evita consultas a disco)
- Procesamiento con NumPy (operaciones vectorizadas)

### Seguridad
- Validación de tipos de archivo
- Límite de tamaño de upload (configurable en FastAPI)
- Logs detallados de cada operación
- Aislamiento de archivos temporales

## Licencia

Ver archivo `LICENSE` para detalles.

## Soporte

Para reportar problemas o sugerencias:
- GitHub Issues: [I-Labs-Chile/ONE-POS-Utilidades](https://github.com/I-Labs-Chile/ONE-POS-Utilidades/issues)

---

**Desarrollado por I-Labs Chile** · Servidor de impresión ESC/POS para retail
- Impresión estrictamente secuencial, sin concurrencia en el envío
- Diseñado para estabilidad en hardware de bajos recursos

