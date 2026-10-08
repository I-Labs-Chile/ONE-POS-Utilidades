# 🖨️ Manual de Impresoras Térmicas ONE-POS (Q-Cube 58mm) — i-Labs Chile

Bienvenido a la guía oficial de uso de las impresoras térmicas de tickets y boletas de **i-Labs Chile**, diseñada especialmente para docentes, estudiantes e instructores del área de **Logística, Operaciones e Innovación de INACAP**.

> 💡 **Nota para no desarrolladores:** No necesitas saber programar ni usar comandos complejos. Todo se maneja de forma visual y sencilla a través de tu navegador de internet (Google Chrome, Edge, etc.).

---

## 📋 ¿Para qué sirve esta herramienta?

Este sistema convierte tu computador en un centro de impresión para la impresora de tickets Q-Cube (58mm):
1. **Servidor de Impresión Web:** Permite arrastrar y soltar cualquier PDF, boleta o imagen en la pantalla de tu computador y se imprimirá automáticamente.
2. **Cabina Fotográfica:** Permite conectar una cámara web, tomar 3 fotos y generar una tira impresa con logo y código QR.

---

## 🚀 Guía de Instalación Rápida Paso a Paso (Windows)

### Paso 1: Descargar los archivos necesarios
Descarga los siguientes dos componentes en tu computador:
1. 📄 **[Driver de la Impresora POS (Haz clic aquí para descargar)](https://github.com/CrisAlva1414/ONE-POS-Driver/raw/refs/heads/main/Driver/Windows%20Driver/POS%20Printer%20Driver%20Setup%20V8.203.exe)**
2. 📦 **[Programa de Impresión i-Labs (Descarga la versión para Windows en Releases)](https://github.com/I-Labs-Chile/ONE-POS-Utilidades/releases)**

---

### Paso 2: Instalar el Driver (Solo se hace 1 vez)
1. Ve a tu carpeta de **Descargas** y haz doble clic en `POS Printer Driver Setup V8.203.exe`.
2. Si aparece una ventana preguntando si deseas permitir cambios, haz clic en **SÍ**.
3. Haz clic en **Next (Siguiente)** ➞ **Install (Instalar)** ➞ **Finish (Finalizar)**.

---

### Paso 3: Descomprimir y Ejecutar el Programa
1. Haz clic derecho sobre el archivo ZIP descargado (`escpos-server-windows-x64-v...zip`) y selecciona **Extraer todo...**.
2. Abre la carpeta que se acaba de crear.
3. Haz doble clic sobre el archivo con ícono **`escpos-server.exe`**.
   * ⚠️ **MUY IMPORTANTE:** Se abrirá una ventana de consola negra. **NO la cierres** (esa ventana mantiene funcionando la impresora). Puedes minimizarla.
   * *Si Windows muestra un aviso de protección:* Haz clic en **Más información** y luego en **Ejecutar de todos modos**.

---

### Paso 4: ¡Imprimir tus archivos!
1. Abre tu navegador web de preferencia (Chrome, Edge o Firefox).
2. Escribe esta dirección arriba en la barra de navegación:
   ```text
   http://localhost:8080
   ```
3. Verás la interfaz de **i-Labs**.
4. Arrastra tu archivo PDF o imagen al recuadro en pantalla... ¡y listo! Tu boleta o ticket saldrá impreso de inmediato.

---

## 📸 Uso Opcional: Cabina Fotográfica con Webcam

Si deseas utilizar la impresora para actividades o eventos con toma de fotos:
1. En la misma carpeta, haz doble clic en **`escpos-cabina.exe`**.
2. Abre en tu navegador la dirección:
   ```text
   http://localhost:8081
   ```
3. Acepta el permiso para usar la cámara web.
4. Presiona la **Barra Espaciadora** o el botón **📸 FOTO** para iniciar la cuenta regresiva.

---

## 🛠️ Solución de Problemas Frecuentes

| Síntoma / Problema | Solución Sencilla |
|---|---|
| **La página web no abre** | Asegúrate de no haber cerrado la ventana negra de `escpos-server.exe`. |
| **La impresora no imprime** | Revisa que el cable USB esté firme y la luz verde de encendido prenda. |
| **El papel sale en blanco** | El rollo de papel térmico está al revés. Da vuelta el rollo de papel. |
| **El texto sale muy claro** | Usa papel térmico de buena calidad (58mm de ancho). |

---

## 📩 Soporte Técnico
- **Desarrollado por:** i-Labs Chile
- **Contacto de Soporte:** `soporte@i-labs.cl`
- **Carpeta de Recursos de i-Labs:** [Google Drive de Documentación](https://drive.google.com/drive/folders/1TxCa-q_Y5rLsmadMrZ1iDFBq5NtVp_1g?usp=sharing)
