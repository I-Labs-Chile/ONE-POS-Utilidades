from typing import Optional, Tuple, Union
from pathlib import Path
import subprocess
import tempfile
import asyncio
import logging
import io
import os

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
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

    def __init__(self):
        self.printer_width_pixels = settings.PRINTER_MAX_PIXELS
        self.printer_dpi = settings.PRINTER_DPI
        
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
        try:
            # Convert to bitmap image
            bitmap = await self._convert_to_bitmap(document_data, document_format)
            
            # Convert bitmap to ESC/POS
            escpos_data = self._bitmap_to_escpos(bitmap)
            
            return escpos_data
            
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            raise ConversionError(f"Failed to convert {document_format}: {e}")
    
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
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_path = os.path.join(temp_dir, "input.pdf")
                png_path = os.path.join(temp_dir, "output-%03d.png")
                
                # Write PDF to temporary file
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_data)
                
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
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    raise ConversionError(f"Ghostscript error: {error_msg}")
                
                # Load first page
                first_page = os.path.join(temp_dir, "output-001.png")
                if not os.path.exists(first_page):
                    raise ConversionError("No output generated by ghostscript")
                
                image = Image.open(first_page)
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
        if not HAS_PILLOW:
            raise ConversionError("Pillow not available for image processing")
        
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            return self._prepare_image_for_thermal(image)
            
        except Exception as e:
            raise ConversionError(f"Image conversion failed: {e}")
    
    def _prepare_image_for_thermal(self, image: Image.Image) -> Image.Image:
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Calculate target size maintaining aspect ratio
        width, height = image.size
        target_width = self.printer_width_pixels
        
        if width > target_width:
            # Scale down maintaining aspect ratio
            scale = target_width / width
            target_height = int(height * scale)
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Convert to grayscale
        image = image.convert('L')
        
        # Apply dithering to convert to 1-bit
        image = image.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        
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
        if image.mode != '1':
            image = image.convert('1')
        
        width, height = image.size
        
        # ESC/POS bitmap printing commands
        escpos_data = io.BytesIO()
        
        # Initialize printer
        escpos_data.write(self.ESC + b'@')  # Initialize printer
        
        # Set line spacing to minimum
        escpos_data.write(self.ESC + b'3' + bytes([0]))
        
        # Convert image to bitmap data
        pixels = list(image.getdata())
        
        # Process image line by line
        for y in range(height):
            line_data = []
            
            # Pack pixels into bytes (8 pixels per byte)
            for x in range(0, width, 8):
                byte_val = 0
                for bit in range(8):
                    if x + bit < width:
                        pixel_index = y * width + x + bit
                        if pixel_index < len(pixels) and pixels[pixel_index] == 0:  # Black pixel
                            byte_val |= (0x80 >> bit)
                line_data.append(byte_val)
            
            # Only print non-empty lines
            if any(b != 0 for b in line_data):
                # ESC/POS bitmap command: ESC * m nL nH data
                escpos_data.write(self.ESC + b'*')
                escpos_data.write(bytes([0]))  # Mode 0 (8-dot single density)
                escpos_data.write(bytes([len(line_data) & 0xFF]))  # nL
                escpos_data.write(bytes([(len(line_data) >> 8) & 0xFF]))  # nH
                escpos_data.write(bytes(line_data))
                escpos_data.write(b'\n')
            else:
                # Empty line
                escpos_data.write(b'\n')
        
        # Feed paper
        escpos_data.write(b'\n\n\n')
        
        # Cut paper (if supported)
        escpos_data.write(self.GS + b'V' + bytes([0]))
        
        return escpos_data.getvalue()
    
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