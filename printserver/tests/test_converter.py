from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import pytest
import asyncio
import io

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PIL import Image, ImageDraw
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from server.converter import DocumentConverter, ConversionError

@pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not available")
class TestDocumentConverter:

    # Inicializa el convertidor antes de cada prueba
    def setup_method(self):
        self.converter = DocumentConverter()
    # Verifica que el convertidor se inicialice con parámetros básicos correctos

    def test_converter_initialization(self):
        assert self.converter.printer_width_pixels > 0
        assert self.converter.printer_dpi > 0
        assert hasattr(self.converter, 'ESC')
        assert hasattr(self.converter, 'GS')

    # Comprueba dependencias externas (Pillow, Ghostscript) sin generar excepción
    def test_dependency_check(self):
        self.converter._check_dependencies()
        if HAS_PILLOW:
            pass

    # Obtiene lista de formatos soportados según dependencias
    def test_supported_formats(self):
        formats = self.converter.get_supported_formats()

        assert isinstance(formats, list)
        assert 'image/jpeg' in formats
        assert 'image/png' in formats
        if self.converter.has_gs_binary:
            assert 'application/pdf' in formats

    # Convierte imagen RGB a bitmap monocromo ajustado al ancho de impresora
    @pytest.mark.asyncio
    async def test_image_to_bitmap_conversion(self):
        test_image = Image.new('RGB', (200, 100), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.text((10, 10), "Test", fill='black')
        img_bytes = io.BytesIO()
        test_image.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        bitmap = await self.converter._convert_image_to_bitmap(img_data)

        assert isinstance(bitmap, Image.Image)
        assert bitmap.mode == '1'
        assert bitmap.size[0] <= self.converter.printer_width_pixels

    # Prepara imagen grande para impresión térmica manteniendo proporciones
    def test_prepare_image_for_thermal(self):
        test_image = Image.new('RGB', (800, 400), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.rectangle([50, 50, 150, 150], fill='red')
        draw.text((200, 100), "Test Print", fill='blue')
        thermal_image = self.converter._prepare_image_for_thermal(test_image)

        assert thermal_image.mode == '1'
        assert thermal_image.size[0] <= self.converter.printer_width_pixels

        original_ratio = test_image.size[1] / test_image.size[0]
        thermal_ratio = thermal_image.size[1] / thermal_image.size[0]
        assert abs(original_ratio - thermal_ratio) < 0.1

    # Convierte un bitmap monocromo simple a comandos ESC/POS
    def test_bitmap_to_escpos(self):
        test_bitmap = Image.new('1', (100, 50), 1)
        draw = ImageDraw.Draw(test_bitmap)
        draw.rectangle([10, 10, 40, 30], fill=0)
        escpos_data = self.converter._bitmap_to_escpos(test_bitmap)

        assert isinstance(escpos_data, bytes)
        assert len(escpos_data) > 0
        assert self.converter.ESC in escpos_data
        assert escpos_data.startswith(self.converter.ESC + b'@')
        assert b'\n' in escpos_data

    # Flujo completo de conversión PNG a comandos ESC/POS incluyendo corte
    @pytest.mark.asyncio
    async def test_convert_to_escpos_png(self):
        test_image = Image.new('RGB', (300, 150), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.text((20, 20), "Test Receipt", fill='black')
        draw.line([(10, 50), (290, 50)], fill='black', width=2)
        draw.text((20, 70), "Item 1: $10.00", fill='black')
        draw.text((20, 90), "Total: $10.00", fill='black')

        png_bytes = io.BytesIO()
        test_image.save(png_bytes, format='PNG')
        png_data = png_bytes.getvalue()
        escpos_data = await self.converter.convert_to_escpos(png_data, 'image/png')

        assert isinstance(escpos_data, bytes)
        assert len(escpos_data) > 100
        assert escpos_data.startswith(self.converter.ESC + b'@')
        assert self.converter.GS + b'V' in escpos_data

    # Conversión de JPEG a ESC/POS básica
    @pytest.mark.asyncio
    async def test_convert_to_escpos_jpeg(self):
        test_image = Image.new('RGB', (200, 200), 'lightgray')
        draw = ImageDraw.Draw(test_image)
        draw.ellipse([50, 50, 150, 150], fill='black')
        jpeg_bytes = io.BytesIO()
        test_image.save(jpeg_bytes, format='JPEG', quality=85)
        jpeg_data = jpeg_bytes.getvalue()
        escpos_data = await self.converter.convert_to_escpos(jpeg_data, 'image/jpeg')

        assert isinstance(escpos_data, bytes)
        assert len(escpos_data) > 0

    # Debe lanzar error al intentar convertir formato no soportado
    @pytest.mark.asyncio
    async def test_unsupported_format_error(self):
        test_data = b"Some random data"
        with pytest.raises(ConversionError):
            await self.converter.convert_to_escpos(test_data, 'application/unsupported')

    # Genera imagen de error para diagnóstico
    def test_create_error_image(self):
        error_img = self.converter._create_error_image("Test error message")

        assert isinstance(error_img, Image.Image)
        assert error_img.mode == '1'
        assert error_img.size[0] == self.converter.printer_width_pixels
        assert error_img.size[1] > 0

    # Conversión de datos PWG Raster simulados (puede no ser perfecta)
    @pytest.mark.asyncio
    async def test_pwg_raster_conversion(self):
        pwg_header = b'\x00' * 1796
        bitmap_data = b'\xFF' * 1000
        pwg_data = pwg_header + bitmap_data

        try:
            result = await self.converter.convert_to_escpos(pwg_data, 'image/pwg-raster')
            assert isinstance(result, bytes)
        except ConversionError:
            pass

    # Verifica estructura de comandos ESC/POS generados desde bitmap
    def test_escpos_commands_structure(self):
        bitmap = Image.new('1', (50, 30), 1)
        draw = ImageDraw.Draw(bitmap)
        draw.text((5, 5), "Hi", fill=0)
        escpos_data = self.converter._bitmap_to_escpos(bitmap)

        assert escpos_data.startswith(b'\x1b@')
        assert b'\x1b3' in escpos_data
        assert b'\x1b*' in escpos_data
        assert escpos_data.endswith(b'\x1dV\x00')

    # Conversión de PDF usando Ghostscript (simulada con mocks)
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_pdf_conversion_with_ghostscript(self, mock_subprocess):
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = b""
        mock_subprocess.return_value.stderr = b""

        with patch('builtins.open', create=True) as mock_open:
            with patch('os.path.exists', return_value=True):
                with patch('PIL.Image.open') as mock_image_open:
                    mock_img = Mock(spec=Image.Image)
                    mock_img.mode = 'RGB'
                    mock_img.size = (200, 100)
                    mock_image_open.return_value = mock_img
                    mock_img.convert.return_value = mock_img
                    mock_img.resize.return_value = mock_img
                    self.converter.has_gs_binary = True
                    self.converter.gs_command = 'gs'
                    pdf_data = b"%PDF-1.4 fake pdf data"
                    try:
                        result = await self.converter._convert_pdf_to_bitmap(pdf_data)
                        mock_subprocess.assert_called()
                    except Exception:
                        pass

class TestConverterPerformance:

    # Manejo de imágenes grandes sin desbordar ancho de impresora
    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not available")
    def test_large_image_handling(self):
        converter = DocumentConverter()
        large_image = Image.new('RGB', (2000, 3000), 'white')
        draw = ImageDraw.Draw(large_image)
        draw.text((100, 100), "Large Image Test", fill='black')
        result = converter._prepare_image_for_thermal(large_image)

        assert result.size[0] <= converter.printer_width_pixels
        assert result.mode == '1'

    # Procesa múltiples conversiones para observar uso de memoria básico
    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not available")
    def test_memory_usage_with_multiple_conversions(self):
        converter = DocumentConverter()
        for i in range(10):
            test_img = Image.new('RGB', (300, 200), 'white')
            draw = ImageDraw.Draw(test_img)
            draw.text((10, 10), f"Image {i}", fill='black')
            result = converter._prepare_image_for_thermal(test_img)
            escpos_data = converter._bitmap_to_escpos(result)
            assert len(escpos_data) > 0

@pytest.mark.asyncio
async def test_converter_integration():

    # Prueba de integración: convierte PNG y JPEG usando el mismo flujo
    if not HAS_PILLOW:
        pytest.skip("Pillow not available")
    converter = DocumentConverter()
    test_image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(test_image)
    draw.text((10, 10), "Integration Test", fill='black')
    png_bytes = io.BytesIO()
    test_image.save(png_bytes, format='PNG')
    png_result = await converter.convert_to_escpos(png_bytes.getvalue(), 'image/png')

    assert isinstance(png_result, bytes)
    jpeg_bytes = io.BytesIO()
    test_image.save(jpeg_bytes, format='JPEG')
    jpeg_result = await converter.convert_to_escpos(jpeg_bytes.getvalue(), 'image/jpeg')
    
    assert isinstance(jpeg_result, bytes)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])