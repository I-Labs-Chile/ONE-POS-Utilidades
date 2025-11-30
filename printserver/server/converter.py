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

try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

# Configuración del logger
logger = logging.getLogger(__name__)

class ConversionError(Exception):
    pass

# Clase responsable de convertir datos entrantes (PDF, imágenes, raster) a comandos ESC/POS listos para impresión térmica.
class DocumentConverter:
    
    def __init__(self):
        self.printer_width_pixels = settings.PRINTER_MAX_PIXELS
        self.printer_dpi = settings.PRINTER_DPI
        logger.info(f"Conversor inicializado: ancho={self.printer_width_pixels}px, dpi={self.printer_dpi}")
        self.ESC = b'\x1b'
        self.GS = b'\x1d'
        self._check_dependencies()
    
    # Verifica disponibilidad de Pillow y binario Ghostscript. Ajusta banderas internas.
    def _check_dependencies(self):
        
        if not HAS_PILLOW:
            logger.warning("Pillow no disponible: conversión de imágenes limitada")
        self.has_gs_binary = self._check_ghostscript_binary()
        if not self.has_gs_binary:
            logger.warning("Ghostscript no encontrado: conversión PDF degradada")
    
    # Busca nombres comunes del ejecutable Ghostscript y retorna True si alguno se puede ejecutar.
    def _check_ghostscript_binary(self) -> bool:
        
        try:
            for gs_cmd in ['gs', 'ghostscript', 'gswin32c', 'gswin64c']:
                try:
                    result = subprocess.run([gs_cmd, '--version'], capture_output=True, timeout=5)
                    if result.returncode == 0:
                        self.gs_command = gs_cmd
                        logger.debug(f"Ghostscript detectado: {gs_cmd}")
                        return True
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue
            return False
        except Exception:
            return False
        
    # Convierte datos a ESC/POS. Pasos: detección de formato, retorno directo si ya es ESC/POS, conversión a bitmap, transformación a comandos.
    async def convert_to_escpos(self, document_data: bytes, document_format: str) -> bytes:
        
        try:
            logger.info(f"Inicio de conversión: formato={document_format}, bytes={len(document_data)}")
            actual_format = document_format
            if document_format == 'application/octet-stream':
                actual_format = self._detect_format(document_data)
                logger.info(f"Formato detectado: {actual_format}")
            if actual_format == 'application/vnd.escpos' or self._is_escpos_data(document_data):
                logger.info("Datos ya en formato ESC/POS: envío directo")
                return document_data
            logger.debug(f"Convirtiendo a bitmap desde {actual_format}...")
            bitmap = await self._convert_to_bitmap(document_data, actual_format)
            logger.info(f"Bitmap generado: {bitmap.size[0]}x{bitmap.size[1]} px")
            logger.debug("Transformando bitmap a ESC/POS...")
            escpos_data = self._bitmap_to_escpos(bitmap)
            logger.info(f"Conversión finalizada: {len(escpos_data)} bytes ESC/POS")
            return escpos_data
        except Exception as e:
            logger.error(f"Fallo en conversión: {e}")
            import traceback
            logger.debug(f"Traza: {traceback.format_exc()}")
            raise ConversionError(f"Fallo al convertir {document_format}: {e}")
    
    # Detecta formato por magic bytes. Retorna MIME o application/octet-stream si desconocido.
    def _detect_format(self, data: bytes) -> str:
        
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
    
    # Verifica presencia de comandos ESC/POS típicos en los primeros bytes.
    def _is_escpos_data(self, data: bytes) -> bool:
        
        if len(data) < 10:
            return False
        escpos_markers = [b'\x1b@', b'\x1b*', b'\x1d', b'\x1ba', b'\x1bE']
        preview = data[:100]
        return any(marker in preview for marker in escpos_markers)
    
    # Detecta PDFs que solo contienen una imagen embebida (JPEG/PNG) para ruta rápida.
    def _is_image_wrapped_pdf(self, pdf_data: bytes) -> bool:
        
        try:
            if b'/DCTDecode' in pdf_data or b'JFIF' in pdf_data:
                logger.debug("PDF con imagen JPEG detectado")
                return True
            if b'/FlateDecode' in pdf_data and b'PNG' in pdf_data:
                logger.debug("PDF con imagen PNG detectado")
                return True
            return False
        except:
            return False
        
    # Intenta extraer bytes de imagen directa (JPEG/PNG) dentro del PDF evitando Ghostscript si es un contenedor simple.
    async def _extract_image_from_pdf(self, pdf_data: bytes) -> Optional[Image.Image]:
        
        try:
            jpeg_start = pdf_data.find(b'\xFF\xD8\xFF')
            if jpeg_start > 0:
                jpeg_end = pdf_data.find(b'\xFF\xD9', jpeg_start)
                if jpeg_end > jpeg_start:
                    jpeg_data = pdf_data[jpeg_start:jpeg_end + 2]
                    logger.info(f"Imagen JPEG extraída: {len(jpeg_data)} bytes")
                    return await self._convert_image_to_bitmap(jpeg_data)
            png_start = pdf_data.find(b'\x89PNG')
            if png_start > 0:
                png_end = pdf_data.find(b'IEND', png_start)
                if png_end > png_start:
                    png_data = pdf_data[png_start:png_end + 8]
                    logger.info(f"Imagen PNG extraída: {len(png_data)} bytes")
                    return await self._convert_image_to_bitmap(png_data)
            return None
        except Exception as e:
            logger.warning(f"No se pudo extraer imagen de PDF: {e}")
            return None
    
    # Normaliza cualquier formato soportado a un bitmap monocromático listo para impresora térmica.
    async def _convert_to_bitmap(self, document_data: bytes, document_format: str) -> Image.Image:
        
        if document_format == "application/pdf":
            return await self._convert_pdf_to_bitmap(document_data)
        elif document_format == "image/pwg-raster":
            return await self._convert_pwg_to_bitmap(document_data)
        elif document_format in ["image/jpeg", "image/png"]:
            return await self._convert_image_to_bitmap(document_data)
        else:
            raise ConversionError(f"Formato no soportado: {document_format}")
    
    # Convierte PDF a imagen usando Ghostscript. Optimiza extracción directa si contiene imagen embebida.
    async def _convert_pdf_to_bitmap(self, pdf_data: bytes) -> Image.Image:
        
        if not self.has_gs_binary:
            raise ConversionError("Ghostscript no disponible para PDF")
        if not HAS_PILLOW:
            raise ConversionError("Pillow no disponible para imágenes")
        logger.debug(f"Procesando PDF ({len(pdf_data)} bytes)")
        try:
            if self._is_image_wrapped_pdf(pdf_data):
                logger.info("PDF con imagen contenedora: extracción directa")
                extracted_image = await self._extract_image_from_pdf(pdf_data)
                if extracted_image:
                    return extracted_image
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_path = os.path.join(temp_dir, "input.pdf")
                png_path = os.path.join(temp_dir, "output-%03d.png")
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_data)
                pdf_size_kb = len(pdf_data) / 1024
                logger.info(f"Procesando PDF: {pdf_size_kb:.1f} KB")
                gs_cmd = [
                    self.gs_command, '-dNOPAUSE', '-dBATCH', '-dSAFER',
                    '-sDEVICE=png16m', f'-r{self.printer_dpi}',
                    '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
                    f'-sOutputFile={png_path}', pdf_path
                ]
                process = await asyncio.create_subprocess_exec(
                    *gs_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                await asyncio.sleep(0.1)
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Error Ghostscript código {process.returncode}: {error_msg}")
                    debug_pdf = Path(__file__).parent.parent / "debug_logs" / f"failed_pdf_{int(time.time())}.pdf"
                    debug_pdf.parent.mkdir(exist_ok=True)
                    with open(debug_pdf, 'wb') as f:
                        f.write(pdf_data)
                    logger.info(f"PDF guardado para depuración: {debug_pdf}")
                    raise ConversionError(f"Error Ghostscript: {error_msg}")
                candidate_paths = []
                max_retries = 10
                retry_delay = 0.05
                for attempt in range(max_retries):
                    first_page = os.path.join(temp_dir, "output-001.png")
                    if os.path.exists(first_page):
                        candidate_paths.append(first_page)
                        break
                    single_page = os.path.join(temp_dir, "output.png")
                    if os.path.exists(single_page):
                        candidate_paths.append(single_page)
                        break
                    for name in sorted(os.listdir(temp_dir)):
                        if name.startswith("output-") and name.endswith(".png"):
                            candidate_paths.append(os.path.join(temp_dir, name))
                            break
                    if candidate_paths:
                        break
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        logger.debug(f"Esperando salida de Ghostscript intento {attempt+1}/{max_retries}")
                if not candidate_paths:
                    retry_png_path = os.path.join(temp_dir, "output.png")
                    gs_retry_cmd = [
                        self.gs_command, '-dNOPAUSE', '-dBATCH', '-dSAFER',
                        '-sDEVICE=png16m', f'-r{self.printer_dpi}',
                        '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
                        f'-sOutputFile={retry_png_path}', pdf_path
                    ]
                    retry_proc = await asyncio.create_subprocess_exec(
                        *gs_retry_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    r_stdout, r_stderr = await retry_proc.communicate()
                    await asyncio.sleep(0.1)
                    if retry_proc.returncode == 0 and os.path.exists(retry_png_path):
                        candidate_paths.append(retry_png_path)
                    else:
                        generated_files = os.listdir(temp_dir)
                        logger.error(f"No se generó imagen tras {max_retries} intentos. Archivos: {generated_files}")
                        raise ConversionError("Ghostscript no produjo salida")
                image = Image.open(candidate_paths[0])
                image.load()
                logger.debug(f"Imagen cargada en memoria: tamaño={image.size}, modo={image.mode}")
                return self._prepare_image_for_thermal(image)
        except Exception as e:
            if isinstance(e, ConversionError):
                raise
            raise ConversionError(f"Conversión PDF fallida: {e}")
    
    # Intenta interpretar PWG Raster simple. Si falla genera imagen de error.
    async def _convert_pwg_to_bitmap(self, pwg_data: bytes) -> Image.Image:
        
        if not HAS_PILLOW:
            raise ConversionError("Pillow no disponible para PWG")
        try:
            header_size = 1796
            if len(pwg_data) < header_size:
                raise ConversionError("Datos PWG inválidos")
            bitmap_data = pwg_data[header_size:]
            width = self.printer_width_pixels
            height = len(bitmap_data) // (width // 8)
            image = Image.frombytes('1', (width, height), bitmap_data[:width * height // 8])
            return image
        except Exception as e:
            logger.warning(f"PWG Raster no procesado: {e}")
            return self._create_error_image("PWG Raster no implementado")
    
    # Convierte imagen (PNG/JPEG) a 1-bit optimizada para impresión térmica.
    async def _convert_image_to_bitmap(self, image_data: bytes) -> Image.Image:
        
        if not HAS_PILLOW:
            raise ConversionError("Pillow no disponible para imágenes")
        try:
            logger.debug(f"Cargando imagen ({len(image_data)} bytes)")
            image = Image.open(io.BytesIO(image_data))
            logger.info(f"Imagen cargada: {image.size[0]}x{image.size[1]} formato={image.format} modo={image.mode}")
            prepared_image = self._prepare_image_for_thermal(image)
            return prepared_image
        except Exception as e:
            logger.error(f"Error al cargar imagen: {e}")
            raise ConversionError(f"Fallo en conversión de imagen: {e}")
    
    # Ajusta imagen a ancho de impresora, mejora contraste/nitidez, convierte a monocromo 1-bit con dithering.
    def _prepare_image_for_thermal(self, image: Image.Image) -> Image.Image:
        
        original_size = image.size
        logger.debug(f"Preparando imagen original {original_size[0]}x{original_size[1]} modo={image.mode}")
        if image.mode not in ('RGB', 'L', '1'):
            logger.debug(f"Conversión de modo {image.mode} a RGB")
            image = image.convert('RGB')
        width, height = image.size
        target_width = self.printer_width_pixels
        if width > target_width:
            scale = target_width / width
            target_height = int(height * scale)
            logger.info(f"Redimensionando {width}x{height} -> {target_width}x{target_height}")
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        elif width < target_width:
            logger.info(f"Imagen más estrecha: se mantiene tamaño {width}x{height}")
        else:
            logger.debug("Ancho ya coincide con la impresora")
        if image.mode != 'L':
            image = image.convert('L')
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.8)
        logger.debug("Contraste aumentado 1.8x")
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        logger.debug("Nitidez aumentada 2.0x")
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)
        logger.debug("Brillo ajustado 1.1x")
        image = image.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        logger.info(f"Imagen final lista: {image.size[0]}x{image.size[1]} 1-bit")
        return image
    
     # Genera imagen simple con mensaje de error cuando no se puede procesar un formato.
    def _create_error_image(self, message: str) -> Image.Image:
       
        if not HAS_PILLOW:
            raise ConversionError("No se puede crear imagen de error sin Pillow")
        width = self.printer_width_pixels
        height = 200
        image = Image.new('1', (width, height), 1)
        draw = ImageDraw.Draw(image)
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 16)
            except:
                try:
                    font = ImageFont.load_default()
                except:
                    pass
        text_lines = message.split('\n')
        y = 10
        for line in text_lines:
            if font:
                draw.text((10, y), line, fill=0, font=font)
                y += 20
            else:
                draw.text((10, y), line, fill=0)
                y += 15
        return image
    
    # Convierte bitmap 1-bit en franjas de 24 px a comandos ESC/POS (modo 33 doble densidad). Incluye inicialización, alineación, avance y corte parcial.
    def _bitmap_to_escpos(self, image: Image.Image) -> bytes:
        
        if image.mode != '1':
            image = image.convert('1')
        width, height = image.size
        logger.info(f"Generando ESC/POS desde bitmap {width}x{height}")
        escpos_data = io.BytesIO()
        escpos_data.write(self.ESC + b'@')               # Inicializar
        logger.debug("Comando: inicializar impresora")
        escpos_data.write(self.ESC + b'3' + bytes([0]))  # Espaciado línea 0
        logger.debug("Comando: espaciado de línea = 0")
        escpos_data.write(self.ESC + b'a' + bytes([1]))  # Centrado
        logger.debug("Comando: alineación centrada")
        y = 0
        strip_count = 0
        while y < height:
            strip_height = min(24, height - y)
            escpos_data.write(self.ESC + b'*' + bytes([33]))
            escpos_data.write(width.to_bytes(2, 'little'))
            for x in range(width):
                for byte_idx in range(3):
                    byte_val = 0
                    for bit_idx in range(8):
                        pixel_y = y + (byte_idx * 8) + bit_idx
                        if pixel_y < height:
                            try:
                                pixel = image.getpixel((x, pixel_y))
                                if pixel == 0:
                                    byte_val |= (1 << (7 - bit_idx))
                            except IndexError:
                                pass
                    escpos_data.write(bytes([byte_val]))
            escpos_data.write(b'\n')
            strip_count += 1
            y += strip_height
        logger.debug(f"Franjas procesadas: {strip_count}")
        escpos_data.write(self.ESC + b'2')  # Restaurar espaciado
        escpos_data.write(self.ESC + b'a' + bytes([0]))  # Alineación izquierda
        logger.debug("Restaurando espaciado y alineación por defecto")
        escpos_data.write(self.ESC + b'd' + bytes([3]))  # Avanzar 3 líneas
        logger.debug("Avance de papel: 3 líneas")
        escpos_data.write(self.GS + b'V' + bytes([66, 0]))  # Corte parcial
        logger.debug("Comando: corte parcial")
        result = escpos_data.getvalue()
        logger.info(f"Total bytes ESC/POS generados: {len(result)}")
        return result
    
    # Método alternativo GS v 0 que envía imagen completa (menos compatible con modelos antiguos).
    def _bitmap_to_escpos_gs_v(self, image: Image.Image) -> bytes:
        
        if image.mode != '1':
            image = image.convert('1')
        width, height = image.size
        logger.info(f"Generando ESC/POS (GS v0) desde bitmap {width}x{height}")
        commands = bytearray()
        commands.extend(self.ESC + b'@')
        logger.debug("Inicialización")
        commands.extend(self.ESC + b'a' + bytes([1]))
        logger.debug("Alineación centrada")
        commands.extend(self.GS + b'v0' + bytes([0]))
        byte_width = (width + 7) // 8
        commands.extend(byte_width.to_bytes(2, 'little'))
        logger.debug(f"Ancho en bytes={byte_width}")
        commands.extend(height.to_bytes(2, 'little'))
        logger.debug(f"Altura={height} px")
        for y in range(height):
            for byte_idx in range(byte_width):
                byte_val = 0
                for bit_idx in range(8):
                    x = (byte_idx * 8) + bit_idx
                    if x < width:
                        pixel = image.getpixel((x, y))
                        if pixel == 0:
                            byte_val |= (1 << (7 - bit_idx))
                commands.append(byte_val)
        logger.debug(f"Datos de imagen generados (sin encabezados): {len(commands) - 10} bytes")
        commands.extend(self.ESC + b'a' + bytes([0]))
        commands.extend(self.ESC + b'd' + bytes([3]))
        commands.extend(self.GS + b'V' + bytes([66, 0]))
        logger.info(f"Bytes totales ESC/POS (GS v0): {len(commands)}")
        return bytes(commands)
    
    # Retorna lista dinámica de formatos soportados según dependencias disponibles.
    def get_supported_formats(self) -> list:
        
        formats = ["image/jpeg", "image/png"]
        if self.has_gs_binary:
            formats.append("application/pdf")
        formats.append("image/pwg-raster")
        return formats

# Prueba rápida creando imagen de ejemplo y convirtiéndola a ESC/POS.
async def test_converter():
        
        if not HAS_PILLOW:
            logger.error("Pillow no disponible para pruebas")
            return
        converter = DocumentConverter()
        test_image = Image.new('RGB', (200, 100), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.text((10, 10), "Test Print", fill='black')
        img_bytes = io.BytesIO()
        test_image.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        try:
            escpos_data = await converter.convert_to_escpos(img_bytes, "image/png")
            logger.info(f"Conversión de prueba OK: {len(escpos_data)} bytes")
            return escpos_data
        except Exception as e:
            logger.error(f"Conversión de prueba fallida: {e}")