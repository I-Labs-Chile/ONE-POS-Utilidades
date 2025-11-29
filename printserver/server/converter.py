from typing import Optional, Tuple, Union
from pathlib import Path
import subprocess
import tempfile
import asyncio
import logging
import io
import os
import time

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import ghostscript
    HAS_GHOSTSCRIPT = True
except ImportError:
    HAS_GHOSTSCRIPT = False

# Try relative import first, fallback to absolute
try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

logger = logging.getLogger(__name__)

class ConversionError(Exception):
    pass

class DocumentConverter:
    """
    Converter INTERNO de documentos a formato nativo de impresora
    
    IMPORTANTE: Este conversor trabaja de forma transparente. Los clientes envían
    documentos estándar (PDF, imágenes) sin saber que se convierten a ESC/POS.
    
    Flujo de conversión (transparente para el cliente):
    1. Recibe documento en formato estándar (PDF, imagen, etc.)
    2. Convierte a imagen bitmap monocromática
    3. Optimiza para impresión de alta calidad (contraste, dithering)
    4. Genera comandos nativos para la impresora (ESC/POS internamente)
    """

    def __init__(self):
        self.printer_width_pixels = settings.PRINTER_MAX_PIXELS
        self.printer_dpi = settings.PRINTER_DPI
        
        logger.info(f"DocumentConverter initialized:")
        logger.info(f"  - Printer width: {self.printer_width_pixels} pixels")
        logger.info(f"  - DPI: {self.printer_dpi}")
        
        # ESC/POS commands
        self.ESC = b'\x1b'
        self.GS = b'\x1d'
        
        # Check dependencies
        self._check_dependencies()
    
    def _check_dependencies(self):
        if not HAS_PILLOW:
            logger.warning("Pillow not available - image processing will be limited")
        
        # Check for ghostscript binary
        self.has_gs_binary = self._check_ghostscript_binary()
        if not self.has_gs_binary:
            logger.warning("Ghostscript binary not found - PDF conversion will be limited")
    
    def _check_ghostscript_binary(self) -> bool:
        try:
            # Try common ghostscript binary names
            for gs_cmd in ['gs', 'ghostscript', 'gswin32c', 'gswin64c']:
                try:
                    result = subprocess.run([gs_cmd, '--version'], 
                                         capture_output=True, timeout=5)
                    if result.returncode == 0:
                        self.gs_command = gs_cmd
                        logger.debug(f"Found ghostscript: {gs_cmd}")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            return False
        except Exception:
            return False
    
    async def convert_to_escpos(self, document_data: bytes, document_format: str) -> bytes:
        """
        Convierte documento a formato ESC/POS
        
        Flujo:
        1. Detecta formato si es 'application/octet-stream'
        2. Si ya es ESC/POS, lo devuelve directamente
        3. Si no, convierte a bitmap y luego a ESC/POS
        
        Args:
            document_data: Datos del documento en bytes
            document_format: Tipo MIME del documento
            
        Returns:
            Comandos ESC/POS listos para enviar a la impresora
        """
        try:
            logger.info(f"Starting conversion: format={document_format}, size={len(document_data)} bytes")
            
            # PASO 1: Detectar formato real si es octet-stream
            actual_format = document_format
            if document_format == 'application/octet-stream':
                actual_format = self._detect_format(document_data)
                logger.info(f"Detected actual format: {actual_format}")
            
            # PASO 2: Si ya es ESC/POS, usar directamente
            if actual_format == 'application/vnd.escpos' or self._is_escpos_data(document_data):
                logger.info("Document is already in ESC/POS format, using directly")
                return document_data
            
            # PASO 3: Convertir a bitmap
            logger.debug(f"Converting {actual_format} to bitmap...")
            bitmap = await self._convert_to_bitmap(document_data, actual_format)
            logger.info(f"Bitmap created: {bitmap.size[0]}x{bitmap.size[1]} pixels")
            
            # PASO 4: Convertir bitmap a ESC/POS
            logger.debug("Converting bitmap to ESC/POS commands...")
            escpos_data = self._bitmap_to_escpos(bitmap)
            logger.info(f"Conversion complete: {len(escpos_data)} bytes of ESC/POS")
            
            return escpos_data
            
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            import traceback
            logger.debug(f"Conversion error traceback: {traceback.format_exc()}")
            raise ConversionError(f"Failed to convert {document_format}: {e}")
    
    def _detect_format(self, data: bytes) -> str:
        """Detecta el formato del documento por magic bytes"""
        if data.startswith(b'%PDF'):
            return 'application/pdf'
        elif data.startswith(b'\xFF\xD8\xFF'):
            return 'image/jpeg'
        elif data.startswith(b'\x89PNG'):
            return 'image/png'
        elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
            return 'image/gif'
        elif data.startswith(b'BM'):
            return 'image/bmp'
        elif b'\x1b' in data[:100] or b'\x1d' in data[:100]:
            return 'application/vnd.escpos'
        else:
            return 'application/octet-stream'
    
    def _is_escpos_data(self, data: bytes) -> bool:
        """Verifica si los datos son comandos ESC/POS"""
        # Buscar comandos ESC/POS comunes en los primeros bytes
        if len(data) < 10:
            return False
        
        escpos_markers = [
            b'\x1b@',      # ESC @ (Initialize)
            b'\x1b*',      # ESC * (Bitmap)
            b'\x1d',       # GS (Group Separator)
            b'\x1ba',      # ESC a (Alignment)
            b'\x1bE',      # ESC E (Bold)
        ]
        
        preview = data[:100]
        return any(marker in preview for marker in escpos_markers)
    
    def _is_image_wrapped_pdf(self, pdf_data: bytes) -> bool:
        """
        Detecta si un PDF contiene simplemente una imagen JPEG/PNG embebida.
        Android a veces envía imágenes envueltas en PDF.
        """
        try:
            # Buscar markers de imágenes embebidas en el PDF
            # JPEG: buscar /DCTDecode o JFIF
            # PNG: buscar /FlateDecode con datos PNG
            if b'/DCTDecode' in pdf_data or b'JFIF' in pdf_data:
                logger.debug("PDF contains embedded JPEG image")
                return True
            if b'/FlateDecode' in pdf_data and b'PNG' in pdf_data:
                logger.debug("PDF contains embedded PNG image")
                return True
            return False
        except:
            return False
    
    async def _extract_image_from_pdf(self, pdf_data: bytes) -> Optional[Image.Image]:
        """
        Intenta extraer una imagen JPEG/PNG directamente de un PDF.
        Más rápido que usar Ghostscript cuando el PDF es solo un wrapper.
        """
        try:
            # Buscar marcador JPEG (FF D8 FF)
            jpeg_start = pdf_data.find(b'\xFF\xD8\xFF')
            if jpeg_start > 0:
                # Buscar final de JPEG (FF D9)
                jpeg_end = pdf_data.find(b'\xFF\xD9', jpeg_start)
                if jpeg_end > jpeg_start:
                    jpeg_data = pdf_data[jpeg_start:jpeg_end + 2]
                    logger.info(f"📷 Extracted JPEG from PDF: {len(jpeg_data)} bytes")
                    return await self._convert_image_to_bitmap(jpeg_data)
            
            # Buscar marcador PNG (89 50 4E 47)
            png_start = pdf_data.find(b'\x89PNG')
            if png_start > 0:
                # PNG termina con IEND + CRC (49 45 4E 44 AE 42 60 82)
                png_end = pdf_data.find(b'IEND', png_start)
                if png_end > png_start:
                    png_data = pdf_data[png_start:png_end + 8]  # +8 para incluir IEND + CRC
                    logger.info(f"📷 Extracted PNG from PDF: {len(png_data)} bytes")
                    return await self._convert_image_to_bitmap(png_data)
            
            return None
        except Exception as e:
            logger.warning(f"Failed to extract image from PDF: {e}")
            return None
    
    async def _convert_to_bitmap(self, document_data: bytes, document_format: str) -> Image.Image:
        if document_format == "application/pdf":
            return await self._convert_pdf_to_bitmap(document_data)
        
        elif document_format == "image/pwg-raster":
            return await self._convert_pwg_to_bitmap(document_data)
        
        elif document_format in ["image/jpeg", "image/png"]:
            return await self._convert_image_to_bitmap(document_data)
        
        else:
            raise ConversionError(f"Unsupported format: {document_format}")
    
    async def _convert_pdf_to_bitmap(self, pdf_data: bytes) -> Image.Image:
        if not self.has_gs_binary:
            raise ConversionError("Ghostscript not available for PDF conversion")
        
        if not HAS_PILLOW:
            raise ConversionError("Pillow not available for image processing")
        
        logger.debug(f"🔄 Converting PDF to bitmap: {len(pdf_data)} bytes")
        
        try:
            # Detección especial: PDF que contiene una imagen JPEG/PNG embebida
            # Android a veces envía imágenes envueltas en PDF
            if self._is_image_wrapped_pdf(pdf_data):
                logger.info("📷 Detected image-wrapped PDF, extracting image directly")
                extracted_image = await self._extract_image_from_pdf(pdf_data)
                if extracted_image:
                    return extracted_image
                # Si falla extracción, continuar con ghostscript normal
            
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_path = os.path.join(temp_dir, "input.pdf")
                png_path = os.path.join(temp_dir, "output-%03d.png")
                
                # Write PDF to temporary file
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_data)
                
                pdf_size_kb = len(pdf_data) / 1024
                logger.info(f"📄 Processing PDF: {pdf_size_kb:.1f}KB ({len(pdf_data)} bytes)")
                logger.debug(f"Converting PDF with ghostscript in temp_dir: {temp_dir}")
                
                # Convert PDF to PNG using ghostscript
                gs_cmd = [
                    self.gs_command,
                    '-dNOPAUSE',
                    '-dBATCH',
                    '-dSAFER',
                    '-sDEVICE=png16m',
                    f'-r{self.printer_dpi}',
                    f'-dTextAlphaBits=4',
                    f'-dGraphicsAlphaBits=4',
                    f'-sOutputFile={png_path}',
                    pdf_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *gs_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                # BUGFIX: Esperar un poco después de que GS termine para asegurar que
                # el sistema operativo haya terminado de escribir el archivo al disco.
                # Esto previene race conditions en impresiones subsecuentes,
                # especialmente con PDFs de ciertos dispositivos Android.
                await asyncio.sleep(0.1)
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Ghostscript error (exit {process.returncode}): {error_msg}")
                    
                    # Guardar PDF problemático para debugging
                    debug_pdf = Path(__file__).parent.parent / "debug_logs" / f"failed_pdf_{int(time.time())}.pdf"
                    debug_pdf.parent.mkdir(exist_ok=True)
                    with open(debug_pdf, 'wb') as f:
                        f.write(pdf_data)
                    logger.info(f"💾 Saved problematic PDF to: {debug_pdf}")
                    
                    raise ConversionError(f"Ghostscript error: {error_msg}")
                
                # Intentar detectar la(s) salida(s) generada(s) por Ghostscript
                # Algunos builds generan 'output.png' para 1 página en vez de 'output-001.png'
                # BUGFIX: Agregar retry loop para manejar delays en escritura del filesystem
                candidate_paths = []
                max_retries = 10
                retry_delay = 0.05  # 50ms entre intentos
                
                for attempt in range(max_retries):
                    first_page = os.path.join(temp_dir, "output-001.png")
                    if os.path.exists(first_page):
                        candidate_paths.append(first_page)
                        break
                    # fallback: output.png (single page)
                    single_page = os.path.join(temp_dir, "output.png")
                    if os.path.exists(single_page):
                        candidate_paths.append(single_page)
                        break
                    # fallback: cualquier output-*.png
                    for name in sorted(os.listdir(temp_dir)):
                        if name.startswith("output-") and name.endswith(".png"):
                            candidate_paths.append(os.path.join(temp_dir, name))
                            break
                    if candidate_paths:
                        break
                    
                    # Si no encontramos nada, esperar un poco antes de reintentar
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        logger.debug(f"Waiting for GS output file, attempt {attempt + 1}/{max_retries}")
                    
                
                if not candidate_paths:
                    # Como último intento, reintentar con salida sin numeración
                    retry_png_path = os.path.join(temp_dir, "output.png")
                    gs_retry_cmd = [
                        self.gs_command,
                        '-dNOPAUSE',
                        '-dBATCH',
                        '-dSAFER',
                        '-sDEVICE=png16m',
                        f'-r{self.printer_dpi}',
                        f'-dTextAlphaBits=4',
                        f'-dGraphicsAlphaBits=4',
                        f'-sOutputFile={retry_png_path}',
                        pdf_path
                    ]
                    retry_proc = await asyncio.create_subprocess_exec(
                        *gs_retry_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    r_stdout, r_stderr = await retry_proc.communicate()
                    await asyncio.sleep(0.1)  # Wait for filesystem
                    if retry_proc.returncode == 0 and os.path.exists(retry_png_path):
                        candidate_paths.append(retry_png_path)
                    else:
                        generated_files = os.listdir(temp_dir)
                        logger.error(f"Expected {first_page} or {retry_png_path} but not found after {max_retries} attempts. Generated files: {generated_files}\nGS stderr: {stderr.decode('utf-8', errors='ignore')}\nRetry stderr: {r_stderr.decode('utf-8', errors='ignore')}")
                        raise ConversionError("No output generated by ghostscript")

                # BUGFIX: Cargar la imagen completamente en memoria ANTES de salir del temp_dir
                # Esto es crítico porque Image.open() tiene carga lazy y si el archivo
                # temporal se elimina (al salir del 'with'), las operaciones subsecuentes
                # fallarán. Esto afecta especialmente PDFs pequeños (529 bytes) que se
                # procesan rápido y salen del context manager antes de que Pillow termine.
                image = Image.open(candidate_paths[0])
                image.load()  # Force cargar toda la imagen en memoria
                logger.debug(f"Loaded image into memory: {image.size}, mode={image.mode}, size={len(pdf_data)} bytes")
                
                # Ahora que está en memoria, podemos procesarla fuera del temp_dir
                return self._prepare_image_for_thermal(image)
                
        except Exception as e:
            if isinstance(e, ConversionError):
                raise
            raise ConversionError(f"PDF conversion failed: {e}")
    
    async def _convert_pwg_to_bitmap(self, pwg_data: bytes) -> Image.Image:        
        if not HAS_PILLOW:
            raise ConversionError("Pillow not available for PWG processing")
        
        try:
            header_size = 1796
            if len(pwg_data) < header_size:
                raise ConversionError("Invalid PWG Raster data")
            
            # Try to interpret remaining data as raw bitmap
            bitmap_data = pwg_data[header_size:]
            
            # Assume standard thermal width
            width = self.printer_width_pixels
            height = len(bitmap_data) // (width // 8)
            
            # Create image from raw data (this is a simplified approach)
            image = Image.frombytes('1', (width, height), bitmap_data[:width * height // 8])
            
            return image
            
        except Exception as e:
            logger.warning(f"PWG Raster parsing failed: {e}")
            # Fallback: create error message image
            return self._create_error_image("PWG Raster parsing not fully implemented")
    
    async def _convert_image_to_bitmap(self, image_data: bytes) -> Image.Image:
        """
        Convierte imagen (JPEG, PNG, etc.) a bitmap 1-bit para impresora térmica
        """
        if not HAS_PILLOW:
            raise ConversionError("Pillow not available for image processing")
        
        try:
            logger.debug(f"Loading image from {len(image_data)} bytes")
            
            # Load image
            image = Image.open(io.BytesIO(image_data))
            logger.info(f"Image loaded: {image.size[0]}x{image.size[1]} pixels, format={image.format}, mode={image.mode}")
            
            # Preparar para impresora térmica
            prepared_image = self._prepare_image_for_thermal(image)
            
            return prepared_image
            
        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            raise ConversionError(f"Image conversion failed: {e}")
    
    def _prepare_image_for_thermal(self, image: Image.Image) -> Image.Image:
        """
        Prepara imagen para impresión de alta calidad
        
        Proceso de optimización:
        1. Convierte a RGB si es necesario
        2. Escala a ancho de impresora (384px) manteniendo aspecto
        3. Mejora contraste y nitidez para mejor calidad de impresión
        4. Convierte a escala de grises
        5. Aplica dithering Floyd-Steinberg para convertir a 1-bit (B&N)
        """
        original_size = image.size
        logger.debug(f"Preparing image: {original_size[0]}x{original_size[1]} pixels, mode={image.mode}")
        
        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'L', '1'):
            logger.debug(f"Converting from {image.mode} to RGB")
            image = image.convert('RGB')
        
        # Calculate target size maintaining aspect ratio
        width, height = image.size
        target_width = self.printer_width_pixels
        
        if width > target_width:
            # Scale down maintaining aspect ratio
            scale = target_width / width
            target_height = int(height * scale)
            logger.info(f"Scaling image: {width}x{height} -> {target_width}x{target_height}")
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        elif width < target_width:
            # Small images: don't upscale, keep original size
            logger.info(f"Image smaller than printer width, keeping original: {width}x{height}")
        else:
            logger.debug(f"Image matches printer width: {width}x{height}")
        
        # Convert to grayscale if not already
        if image.mode != 'L':
            image = image.convert('L')
        
        # MEJORA 1: Aumentar contraste para impresión de alta calidad
        # Las impresoras monocromáticas necesitan mayor contraste
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.8)  # Aumentar contraste 80%
        logger.debug("Applied contrast enhancement: 1.8x")
        
        # MEJORA 2: Aumentar nitidez para mejor detalle
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)  # Duplicar nitidez
        logger.debug("Applied sharpness enhancement: 2.0x")
        
        # MEJORA 3: Ajustar brillo si es necesario (opcional)
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)  # Aumentar brillo ligeramente
        logger.debug("Applied brightness enhancement: 1.1x")
        
        # MEJORA 4: Aplicar dithering Floyd-Steinberg para convertir a 1-bit
        # Esto distribuye el error de cuantización para mejor calidad visual
        image = image.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        logger.info(f"Image prepared for printing: {image.size[0]}x{image.size[1]} pixels, 1-bit B&W")
        
        return image
    
    def _create_error_image(self, message: str) -> Image.Image:
        if not HAS_PILLOW:
            raise ConversionError("Cannot create error image without Pillow")
        
        # Create simple text image
        width = self.printer_width_pixels
        height = 200  # Fixed height for error messages
        
        image = Image.new('1', (width, height), 1)  # White background
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        font = None
        try:
            # Try to find a system font
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 16)
            except:
                try:
                    font = ImageFont.load_default()
                except:
                    pass  # Use default drawing
        
        # Draw error message
        text_lines = message.split('\n')
        y = 10
        
        for line in text_lines:
            if font:
                draw.text((10, y), line, fill=0, font=font)
                y += 20
            else:
                # Fallback text drawing
                draw.text((10, y), line, fill=0)
                y += 15
        
        return image
    
    def _bitmap_to_escpos(self, image: Image.Image) -> bytes:
        """
        Convierte imagen bitmap a comandos nativos de impresora (ESC/POS)
        
        NOTA INTERNA: Este método genera comandos ESC/POS, pero el cliente
        no necesita saber esto. Para el cliente es una "impresora genérica".
        
        Usa el método ESC * 33 (24-dot double-density) por alta compatibilidad.
        Procesa la imagen en franjas de 24 píxeles de alto.
        
        Formato de comandos:
        - ESC @ : Inicializar impresora
        - ESC 3 n : Establecer espaciado de línea
        - ESC a n : Alineación (0=izq, 1=centro, 2=der)
        - ESC * m nL nH [data] : Imprimir bitmap
        - GS V m : Cortar papel
        """
        if image.mode != '1':
            image = image.convert('1')
        
        width, height = image.size
        logger.info(f"Converting bitmap to ESC/POS: {width}x{height} pixels")
        
        # ESC/POS bitmap printing commands
        escpos_data = io.BytesIO()
        
        # PASO 1: Inicializar impresora
        escpos_data.write(self.ESC + b'@')  # ESC @ : Initialize printer
        logger.debug("Added: Initialize printer (ESC @)")
        
        # PASO 2: Configurar espaciado de línea a 0 para imágenes
        escpos_data.write(self.ESC + b'3' + bytes([0]))  # ESC 3 n : Set line spacing to n/180 inch
        logger.debug("Added: Set line spacing to 0 (ESC 3 0)")
        
        # PASO 3: Centrar la imagen
        escpos_data.write(self.ESC + b'a' + bytes([1]))  # ESC a 1 : Center alignment
        logger.debug("Added: Center alignment (ESC a 1)")
        
        # PASO 4: Procesar imagen en franjas de 24 píxeles (método más compatible)
        y = 0
        strip_count = 0
        
        while y < height:
            # Determinar altura de la franja (máximo 24 píxeles o lo que quede)
            strip_height = min(24, height - y)
            
            # ESC * m nL nH d1...dk
            # m = 33 (24-dot double-density, 203 DPI)
            # nL, nH = ancho en bytes (little-endian)
            escpos_data.write(self.ESC + b'*' + bytes([33]))  # Mode 33 = 24-dot double-density
            escpos_data.write(width.to_bytes(2, 'little'))  # Width in dots (little-endian)
            
            # Procesar cada columna de la franja
            for x in range(width):
                # Para cada byte en la columna (hasta 3 bytes para 24 píxeles)
                for byte_idx in range(3):  # 3 bytes = 24 bits
                    byte_val = 0
                    for bit_idx in range(8):
                        pixel_y = y + (byte_idx * 8) + bit_idx
                        if pixel_y < height:
                            try:
                                pixel = image.getpixel((x, pixel_y))
                                # Para imágenes 1-bit: 0 = negro, 255 = blanco
                                # Para ESC/POS: 1 = negro, 0 = blanco
                                if pixel == 0:  # Píxel negro
                                    byte_val |= (1 << (7 - bit_idx))
                            except IndexError:
                                pass  # Pixel fuera de rango, dejar en blanco
                    
                    escpos_data.write(bytes([byte_val]))
            
            # Line feed después de cada franja
            escpos_data.write(b'\n')
            
            strip_count += 1
            y += strip_height
        
        logger.debug(f"Processed {strip_count} strips of 24 pixels")
        
        # PASO 5: Restaurar configuración
        escpos_data.write(self.ESC + b'2')  # ESC 2 : Reset line spacing to default
        escpos_data.write(self.ESC + b'a' + bytes([0]))  # ESC a 0 : Left alignment
        logger.debug("Added: Reset line spacing and alignment")
        
        # PASO 6: Avanzar papel
        escpos_data.write(self.ESC + b'd' + bytes([3]))  # ESC d 3 : Feed 3 lines
        logger.debug("Added: Feed 3 lines (ESC d 3)")
        
        # PASO 7: Cortar papel (corte parcial si está soportado)
        escpos_data.write(self.GS + b'V' + bytes([66, 0]))  # GS V 66 0 : Partial cut
        logger.debug("Added: Partial cut (GS V 66 0)")
        
        result = escpos_data.getvalue()
        logger.info(f"Generated {len(result)} bytes of ESC/POS commands")
        
        return result
    
    def _bitmap_to_escpos_gs_v(self, image: Image.Image) -> bytes:
        """
        Método alternativo usando GS v 0 (más moderno pero menos compatible)
        
        Este método es más simple pero puede no funcionar en impresoras antiguas.
        Usa GS v 0 que envía la imagen completa de una vez.
        """
        if image.mode != '1':
            image = image.convert('1')
        
        width, height = image.size
        logger.info(f"Converting bitmap to ESC/POS (GS v 0 method): {width}x{height} pixels")
        
        commands = bytearray()
        
        # Initialize
        commands.extend(self.ESC + b'@')
        logger.debug("Added: Initialize printer")
        
        # Center align
        commands.extend(self.ESC + b'a' + bytes([1]))
        logger.debug("Added: Center alignment")
        
        # GS v 0 m xL xH yL yH d1...dk
        # m = mode (0 = normal, 1 = double width, 2 = double height, 3 = quadruple)
        commands.extend(self.GS + b'v0' + bytes([0]))  # Normal mode
        
        # Width in bytes (cada byte = 8 píxeles horizontales)
        byte_width = (width + 7) // 8
        commands.extend(byte_width.to_bytes(2, 'little'))
        logger.debug(f"Image width: {byte_width} bytes ({width} pixels)")
        
        # Height in dots
        commands.extend(height.to_bytes(2, 'little'))
        logger.debug(f"Image height: {height} pixels")
        
        # Image data (fila por fila)
        for y in range(height):
            for byte_idx in range(byte_width):
                byte_val = 0
                for bit_idx in range(8):
                    x = (byte_idx * 8) + bit_idx
                    if x < width:
                        pixel = image.getpixel((x, y))
                        if pixel == 0:  # Negro
                            byte_val |= (1 << (7 - bit_idx))
                commands.append(byte_val)
        
        logger.debug(f"Generated {len(commands) - 10} bytes of image data")
        
        # Reset alignment
        commands.extend(self.ESC + b'a' + bytes([0]))
        
        # Feed and cut
        commands.extend(self.ESC + b'd' + bytes([3]))
        commands.extend(self.GS + b'V' + bytes([66, 0]))
        
        logger.info(f"Generated {len(commands)} bytes of ESC/POS commands (GS v 0 method)")
        return bytes(commands)
    
    def get_supported_formats(self) -> list:
        formats = ["image/jpeg", "image/png"]
        
        if self.has_gs_binary:
            formats.append("application/pdf")
        
        # PWG Raster is partially supported
        formats.append("image/pwg-raster")
        
        return formats

# Test function to validate converter
async def test_converter():
    if not HAS_PILLOW:
        logger.error("Pillow not available for testing")
        return
    
    converter = DocumentConverter()
    
    # Create a test image
    test_image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(test_image)
    draw.text((10, 10), "Test Print", fill='black')
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    test_image.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()
    
    # Convert to ESC/POS
    try:
        escpos_data = await converter.convert_to_escpos(img_bytes, "image/png")
        logger.info(f"Test conversion successful: {len(escpos_data)} bytes")
        return escpos_data
    except Exception as e:
        logger.error(f"Test conversion failed: {e}")
        return None

if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_converter())