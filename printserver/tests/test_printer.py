#!/usr/bin/env python3

from hardware.usb_detector import USBPrinterDetector
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    print("=" * 70)
    print("USB PRINTER DIAGNOSTIC TOOL")
    print("=" * 70)
    print()
    
    detector = USBPrinterDetector()
    
    print("🔍 Scanning for USB printers...")
    print()
    
    printers = detector.scan_for_printers()
    
    if not printers:
        print("❌ No printers found!")
        print()
        print("Troubleshooting:")
        print("  1. Check USB connection")
        print("  2. Verify printer is powered on")
        print("  3. Check permissions: ls -l /dev/usb/lp*")
        print("  4. Add user to lp group: sudo usermod -a -G lp $USER")
        print("  5. Install usbutils: sudo apt install usbutils")
        return 1
    
    print(f"✅ Found {len(printers)} printer(s):")
    print()
    
    for i, printer in enumerate(printers, 1):
        print(f"Printer #{i}:")
        print(f"  Device Path:  {printer.device_path}")
        print(f"  Name:         {printer.friendly_name}")
        
        if printer.vendor_id:
            print(f"  Vendor ID:    {printer.vendor_id}")
        if printer.product_id:
            print(f"  Product ID:   {printer.product_id}")
        if printer.manufacturer:
            print(f"  Manufacturer: {printer.manufacturer}")
        if printer.product:
            print(f"  Product:      {printer.product}")
        if printer.serial:
            print(f"  Serial:       {printer.serial}")
        
        is_thermal = detector.is_thermal_printer(printer)
        print(f"  Type:         {'🔥 Thermal' if is_thermal else '🖨️  Standard'}")
        
        # Test connection
        print(f"  Testing connection...", end=' ')
        if detector.test_printer_connection(printer.device_path):
            print("✅ OK")
        else:
            print("❌ FAILED")
            print(f"    Try: sudo chmod 666 {printer.device_path}")
        
        print()
    
    print("=" * 70)
    print("Recommendation:")
    if printers:
        primary = printers[0]
        print(f"  Use: {primary.device_path}")
        print(f"  Name: {primary.friendly_name}")
    print("=" * 70)
    return 0

if __name__ == '__main__':
    sys.exit(main())