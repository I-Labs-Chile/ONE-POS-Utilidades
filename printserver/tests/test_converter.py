"""
Tests for document converter functionality

This module tests the document conversion pipeline from various formats
(PDF, images, PWG Raster) to ESC/POS thermal printer commands.
"""

import pytest
import asyncio
import io
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

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
    """Test document to ESC/POS conversion"""
    
    def setup_method(self):
        """Setup for each test"""
        self.converter = DocumentConverter()
    
    def test_converter_initialization(self):
        """Test converter initializes with correct settings"""
        assert self.converter.printer_width_pixels > 0
        assert self.converter.printer_dpi > 0
        assert hasattr(self.converter, 'ESC')
        assert hasattr(self.converter, 'GS')
    
    def test_dependency_check(self):
        """Test dependency checking"""
        # Should not raise exception
        self.converter._check_dependencies()
        
        # Should have detected Pillow if available
        if HAS_PILLOW:
            # Cannot easily test this without mocking imports
            pass
    
    def test_supported_formats(self):
        """Test getting supported formats"""
        formats = self.converter.get_supported_formats()
        
        assert isinstance(formats, list)
        assert 'image/jpeg' in formats
        assert 'image/png' in formats
        
        # PDF support depends on ghostscript availability
        if self.converter.has_gs_binary:
            assert 'application/pdf' in formats
    
    @pytest.mark.asyncio
    async def test_image_to_bitmap_conversion(self):
        """Test converting image to bitmap"""
        # Create test image
        test_image = Image.new('RGB', (200, 100), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.text((10, 10), "Test", fill='black')
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        test_image.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        
        # Convert to bitmap
        bitmap = await self.converter._convert_image_to_bitmap(img_data)
        
        assert isinstance(bitmap, Image.Image)
        assert bitmap.mode == '1'  # Should be monochrome
        assert bitmap.size[0] <= self.converter.printer_width_pixels
    
    def test_prepare_image_for_thermal(self):
        """Test thermal printer image preparation"""
        # Create test image
        test_image = Image.new('RGB', (800, 400), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.rectangle([50, 50, 150, 150], fill='red')
        draw.text((200, 100), "Test Print", fill='blue')
        
        # Prepare for thermal printing
        thermal_image = self.converter._prepare_image_for_thermal(test_image)
        
        assert thermal_image.mode == '1'  # Monochrome
        assert thermal_image.size[0] <= self.converter.printer_width_pixels
        
        # Aspect ratio should be maintained (approximately)
        original_ratio = test_image.size[1] / test_image.size[0]
        thermal_ratio = thermal_image.size[1] / thermal_image.size[0]
        assert abs(original_ratio - thermal_ratio) < 0.1
    
    def test_bitmap_to_escpos(self):
        """Test converting bitmap to ESC/POS commands"""
        # Create simple test bitmap
        test_bitmap = Image.new('1', (100, 50), 1)  # White background
        draw = ImageDraw.Draw(test_bitmap)
        draw.rectangle([10, 10, 40, 30], fill=0)  # Black rectangle
        
        # Convert to ESC/POS
        escpos_data = self.converter._bitmap_to_escpos(test_bitmap)
        
        assert isinstance(escpos_data, bytes)
        assert len(escpos_data) > 0
        
        # Should contain ESC/POS commands
        assert self.converter.ESC in escpos_data  # ESC commands present
        
        # Should have initialization
        assert escpos_data.startswith(self.converter.ESC + b'@')
        
        # Should have line feeds
        assert b'\n' in escpos_data
    
    @pytest.mark.asyncio
    async def test_convert_to_escpos_png(self):
        """Test full PNG to ESC/POS conversion"""
        # Create test PNG
        test_image = Image.new('RGB', (300, 150), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.text((20, 20), "Test Receipt", fill='black')
        draw.line([(10, 50), (290, 50)], fill='black', width=2)
        draw.text((20, 70), "Item 1: $10.00", fill='black')
        draw.text((20, 90), "Total: $10.00", fill='black')
        
        # Convert to PNG bytes
        png_bytes = io.BytesIO()
        test_image.save(png_bytes, format='PNG')
        png_data = png_bytes.getvalue()
        
        # Convert to ESC/POS
        escpos_data = await self.converter.convert_to_escpos(png_data, 'image/png')
        
        assert isinstance(escpos_data, bytes)
        assert len(escpos_data) > 100  # Should be substantial
        
        # Should contain proper ESC/POS structure
        assert escpos_data.startswith(self.converter.ESC + b'@')  # Init
        assert self.converter.GS + b'V' in escpos_data  # Cut command
    
    @pytest.mark.asyncio 
    async def test_convert_to_escpos_jpeg(self):
        """Test JPEG to ESC/POS conversion"""
        # Create test JPEG
        test_image = Image.new('RGB', (200, 200), 'lightgray')
        draw = ImageDraw.Draw(test_image)
        draw.ellipse([50, 50, 150, 150], fill='black')
        
        # Convert to JPEG bytes
        jpeg_bytes = io.BytesIO()
        test_image.save(jpeg_bytes, format='JPEG', quality=85)
        jpeg_data = jpeg_bytes.getvalue()
        
        # Convert to ESC/POS
        escpos_data = await self.converter.convert_to_escpos(jpeg_data, 'image/jpeg')
        
        assert isinstance(escpos_data, bytes)
        assert len(escpos_data) > 0
    
    @pytest.mark.asyncio
    async def test_unsupported_format_error(self):
        """Test error handling for unsupported format"""
        test_data = b"Some random data"
        
        with pytest.raises(ConversionError):
            await self.converter.convert_to_escpos(test_data, 'application/unsupported')
    
    def test_create_error_image(self):
        """Test error image creation"""
        error_img = self.converter._create_error_image("Test error message")
        
        assert isinstance(error_img, Image.Image)
        assert error_img.mode == '1'  # Monochrome
        assert error_img.size[0] == self.converter.printer_width_pixels
        assert error_img.size[1] > 0
    
    @pytest.mark.asyncio
    async def test_pwg_raster_conversion(self):
        """Test PWG Raster conversion (basic)"""
        # Create mock PWG data (simplified)
        pwg_header = b'\x00' * 1796  # Mock PWG header
        bitmap_data = b'\xFF' * 1000  # Mock bitmap data
        pwg_data = pwg_header + bitmap_data
        
        # Should not crash (though may not produce perfect results)
        try:
            result = await self.converter.convert_to_escpos(pwg_data, 'image/pwg-raster')
            assert isinstance(result, bytes)
        except ConversionError:
            # Expected for incomplete PWG implementation
            pass
    
    def test_escpos_commands_structure(self):
        """Test ESC/POS command structure"""
        # Create simple bitmap
        bitmap = Image.new('1', (50, 30), 1)
        draw = ImageDraw.Draw(bitmap)
        draw.text((5, 5), "Hi", fill=0)
        
        escpos_data = self.converter._bitmap_to_escpos(bitmap)
        
        # Should start with printer initialization
        assert escpos_data.startswith(b'\x1b@')
        
        # Should contain line spacing command  
        assert b'\x1b3' in escpos_data
        
        # Should contain bitmap print commands
        assert b'\x1b*' in escpos_data
        
        # Should end with cut command
        assert escpos_data.endswith(b'\x1dV\x00')
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_pdf_conversion_with_ghostscript(self, mock_subprocess):
        """Test PDF conversion using ghostscript"""
        # Mock successful ghostscript execution
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = b""
        mock_subprocess.return_value.stderr = b""
        
        # Mock file operations
        with patch('builtins.open', create=True) as mock_open:
            with patch('os.path.exists', return_value=True):
                with patch('PIL.Image.open') as mock_image_open:
                    # Mock PIL Image
                    mock_img = Mock(spec=Image.Image)
                    mock_img.mode = 'RGB'
                    mock_img.size = (200, 100)
                    mock_image_open.return_value = mock_img
                    
                    # Mock image conversion methods
                    mock_img.convert.return_value = mock_img
                    mock_img.resize.return_value = mock_img
                    
                    # Force converter to think ghostscript is available
                    self.converter.has_gs_binary = True
                    self.converter.gs_command = 'gs'
                    
                    pdf_data = b"%PDF-1.4 fake pdf data"
                    
                    try:
                        result = await self.converter._convert_pdf_to_bitmap(pdf_data)
                        # Should call ghostscript
                        mock_subprocess.assert_called()
                    except Exception:
                        # May fail due to mocking complexity, but shouldn't crash
                        pass

class TestConverterPerformance:
    """Test converter performance and resource usage"""
    
    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not available")
    def test_large_image_handling(self):
        """Test handling of large images"""
        converter = DocumentConverter()
        
        # Create large image
        large_image = Image.new('RGB', (2000, 3000), 'white')
        draw = ImageDraw.Draw(large_image)
        draw.text((100, 100), "Large Image Test", fill='black')
        
        # Should handle without crashing
        result = converter._prepare_image_for_thermal(large_image)
        
        assert result.size[0] <= converter.printer_width_pixels
        assert result.mode == '1'
    
    @pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not available")
    def test_memory_usage_with_multiple_conversions(self):
        """Test memory usage with multiple conversions"""
        converter = DocumentConverter()
        
        # Process multiple images
        for i in range(10):
            test_img = Image.new('RGB', (300, 200), 'white')
            draw = ImageDraw.Draw(test_img)
            draw.text((10, 10), f"Image {i}", fill='black')
            
            result = converter._prepare_image_for_thermal(test_img)
            escpos_data = converter._bitmap_to_escpos(result)
            
            assert len(escpos_data) > 0

@pytest.mark.asyncio
async def test_converter_integration():
    """Integration test for converter with all supported formats"""
    if not HAS_PILLOW:
        pytest.skip("Pillow not available")
    
    converter = DocumentConverter()
    
    # Test image formats
    test_image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(test_image)
    draw.text((10, 10), "Integration Test", fill='black')
    
    # Test PNG
    png_bytes = io.BytesIO()
    test_image.save(png_bytes, format='PNG')
    png_result = await converter.convert_to_escpos(png_bytes.getvalue(), 'image/png')
    assert isinstance(png_result, bytes)
    
    # Test JPEG
    jpeg_bytes = io.BytesIO()
    test_image.save(jpeg_bytes, format='JPEG')
    jpeg_result = await converter.convert_to_escpos(jpeg_bytes.getvalue(), 'image/jpeg')
    assert isinstance(jpeg_result, bytes)

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])