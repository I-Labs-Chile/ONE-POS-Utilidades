# IPP Print Server for Thermal Printers

Universal IPP (Internet Printing Protocol) server for thermal ESC/POS printers with driverless support. Compatible with Chrome, Android, Linux CUPS, macOS AirPrint, and iOS.

## 🚀 Features

- **Universal Compatibility**: Works with Chrome, Android (Mopria), Linux (CUPS), macOS (AirPrint), and iOS
- **Driverless Operation**: No driver installation required on client devices
- **Multiple Document Formats**: Supports PDF, JPEG, PNG, and PWG Raster
- **Auto-Discovery**: Uses mDNS/DNS-SD for automatic printer discovery
- **USB Thermal Printers**: ESC/POS compatible thermal receipt printers
- **Portable Executable**: Single-file executable for Windows and Linux using PyInstaller
- **Web Interface**: Built-in web interface for configuration and status

## 📋 Requirements

### System Requirements
- **Python**: 3.7 or higher
- **Operating System**: Windows 10+, Linux, macOS 10.14+
- **USB Thermal Printer**: ESC/POS compatible (58mm, 80mm, or 110mm)

### Supported Thermal Printers
- Epson TM series (TM-T20, TM-T82, etc.)
- Star TSP series (TSP650, TSP700, TSP800)
- Citizen CT-S310 series
- Generic ESC/POS thermal printers

### Dependencies
- **Required**: `aiohttp`, `zeroconf`, `pyusb`, `pillow`
- **Optional**: `ghostscript` (for PDF conversion), `psutil` (monitoring)

## 🛠️ Installation

### Option 1: Download Pre-built Executable
Download the latest release for your platform:
- `printserver-windows.exe` - Windows 10/11
- `printserver-linux` - Linux x64
- `printserver-macos` - macOS (Intel/Apple Silicon)

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/your-repo/ipp-print-server.git
cd ipp-print-server/printserver

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Ghostscript (optional, for PDF support)
# Ubuntu/Debian: sudo apt-get install ghostscript
# Windows: Download from https://www.ghostscript.com/download/
# macOS: brew install ghostscript
```

### Option 3: Build Executable

```bash
# Linux/macOS
./build.sh

# Windows
build.bat

# Custom build options
./build.sh --onedir --version 1.0.0
```

## 🚦 Quick Start

### 1. Connect Your Thermal Printer
- Connect USB thermal printer to your computer
- Ensure printer is powered on and has paper loaded
- On Linux, you may need to add your user to the `lp` group:
  ```bash
  sudo usermod -a -G lp $USER
  ```

### 2. Start the Server

#### Using Pre-built Executable:
```bash
# Windows
printserver.exe

# Linux/macOS
./printserver
```

#### Using Python:
```bash
python main.py
```

### 3. Verify Operation

The server will start on port 631 (standard IPP port) and display:
```
IPP Server started on http://0.0.0.0:631
Printer URI: ipp://your-ip:631/ipp/printer
```

Visit `http://localhost:631` in your browser to see the web interface.

## 📱 Client Setup

### Chrome Browser
1. Chrome automatically discovers IPP printers via mDNS
2. Go to Print → More destinations → Your thermal printer should appear

### Android Devices
1. Ensure Android device is on same network
2. Go to Settings → Connected devices → Printing → Default Print Service
3. Your printer should appear automatically via Mopria

### Linux (CUPS)
```bash
# Auto-discover and add printer
sudo lpadmin -p ThermalPrinter -E -v ipp://your-server-ip:631/ipp/printer -m everywhere

# Or use CUPS web interface
# Visit http://localhost:631 → Administration → Add Printer
```

### macOS/iOS (AirPrint)
1. System Preferences → Printers & Scanners → Add Printer
2. Your thermal printer should appear under AirPrint printers
3. iOS devices will automatically discover the printer

### Windows 10/11
1. Settings → Devices → Printers & scanners → Add a printer or scanner
2. Select "The printer that I want isn't listed"
3. Choose "Add a printer using a TCP/IP address or hostname"
4. Enter: `ipp://your-server-ip:631/ipp/printer`

## ⚙️ Configuration

### Environment Variables
```bash
# Server configuration
export PRINTSERVER_HOST=0.0.0.0
export PRINTSERVER_PORT=631

# Printer configuration  
export PRINTER_NAME="Thermal Printer"
export PRINTER_INFO="ESC/POS Thermal Receipt Printer"
export PRINTER_LOCATION="Office"
export PRINTER_WIDTH_MM=80
export PRINTER_DPI=203

# USB configuration (optional)
export USB_VENDOR_ID=04b8    # Epson
export USB_PRODUCT_ID=0202   # TM-T20

# Logging
export LOG_LEVEL=INFO
export LOG_FILE=/var/log/printserver.log
```

### Command Line Options
```bash
# Basic usage
python main.py

# Custom host and port
python main.py --host 192.168.1.100 --port 8631

# Enable debug logging
python main.py --debug --log-level DEBUG

# Disable mDNS announcement
python main.py --no-mdns

# Log to file
python main.py --log-file server.log

# Health check
python main.py --health-check

# Status report
python main.py --status
```

## 🔧 Troubleshooting

### Printer Not Found
```bash
# Check USB devices
lsusb  # Linux
# Look for your printer vendor/product ID

# Test USB permissions (Linux)
sudo dmesg | grep -i printer
ls -la /dev/usb/lp*

# Health check
python main.py --health-check
```

### Network Discovery Issues
```bash
# Check mDNS services
avahi-browse -at  # Linux
dns-sd -B _ipp._tcp  # macOS

# Test IPP endpoint
curl -X POST -H "Content-Type: application/ipp" \
  http://your-server:631/ipp/printer --data-binary @- < /dev/null
```

### PDF Conversion Issues
```bash
# Install Ghostscript
sudo apt-get install ghostscript  # Ubuntu/Debian
brew install ghostscript          # macOS

# Test Ghostscript
gs --version
```

### Permission Issues (Linux)
```bash
# Add user to groups
sudo usermod -a -G lp,dialout $USER

# Fix USB permissions
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_ipp.py -v

# Run with coverage
pytest tests/ --cov=server --cov-report=html
```

### Manual Testing

#### Test IPP Communication
```bash
# Using ipptool (if available)
ipptool -tv ipp://localhost:631/ipp/printer get-printer-attributes.test

# Using curl for Get-Printer-Attributes
curl -X POST -H "Content-Type: application/ipp" \
  --data-binary "$(echo -e '\x02\x01\x00\x0b\x00\x00\x00\x01\x01G\x00\x12attributes-charset\x00\x05utf-8H\x00\x1battributes-natural-language\x00\x02en\x03')" \
  http://localhost:631/ipp/printer
```

#### Test Document Conversion
```bash
# Test converter directly
python -c "
from server.converter import DocumentConverter
import asyncio

async def test():
    converter = DocumentConverter()
    # Test with a simple image file
    with open('test.png', 'rb') as f:
        escpos = await converter.convert_to_escpos(f.read(), 'image/png')
    print(f'Converted to {len(escpos)} bytes of ESC/POS')

asyncio.run(test())
"
```

### Integration Testing
```bash
# Start server
python main.py --debug &
SERVER_PID=$!

# Test health
curl http://localhost:631/
python main.py --health-check

# Stop server
kill $SERVER_PID
```

## 📊 Monitoring

### Web Interface
Visit `http://your-server:631` to access:
- Printer status and information
- Active print jobs
- Server statistics
- Configuration details

### Health Checks
```bash
# Quick health check
python main.py --health-check

# Detailed status
python main.py --status

# Monitor logs
tail -f /var/log/printserver.log
```

### Performance Monitoring
The server includes built-in performance monitoring:
- Request counts and timing
- Error rates
- Memory usage (if psutil available)
- Active job tracking

## 🔒 Security Considerations

- **Network Access**: Server binds to all interfaces by default (0.0.0.0)
- **Authentication**: No authentication required by default (standard for network printers)
- **Firewall**: Ensure port 631 is accessible from client devices
- **USB Access**: Requires appropriate USB permissions on Linux

## 📝 API Reference

### IPP Operations Supported
- `Get-Printer-Attributes` - Get printer capabilities and status
- `Print-Job` - Submit document for printing
- `Validate-Job` - Validate print job without printing
- `Get-Jobs` - List active print jobs
- `Cancel-Job` - Cancel a print job

### Document Formats Supported
- `application/pdf` - PDF documents (requires Ghostscript)
- `image/jpeg` - JPEG images
- `image/png` - PNG images
- `image/pwg-raster` - PWG Raster format

### mDNS Services Published
- `_ipp._tcp.local` - Standard IPP service
- `_printer._tcp.local` - Generic printer service
- `_pdl-datastream._tcp.local` - Print data stream service

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes and add tests
4. Run tests: `pytest tests/`
5. Commit changes: `git commit -m "Add your feature"`
6. Push branch: `git push origin feature/your-feature`
7. Submit a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [RFC 8011](https://tools.ietf.org/html/rfc8011) - Internet Printing Protocol/1.1
- [AirPrint Specification](https://developer.apple.com/airprint/) - Apple AirPrint Documentation
- [Mopria Alliance](https://mopria.org/) - Universal Print Standard
- [ESC/POS Command Reference](https://reference.epson-biz.com/modules/ref_escpos/) - ESC/POS Commands

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation**: [Wiki](https://github.com/your-repo/wiki)
- **Discord**: [Community Server](https://discord.gg/your-server)

---

**Made with ❤️ for the thermal printing community**