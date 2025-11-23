#!/usr/bin/env python3
"""
IPP Print Server - Main Entry Point

Universal IPP Print Server for thermal printers with driverless support.
Compatible with Chrome, Android, Linux CUPS, macOS, and iOS AirPrint.

Usage:
    python main.py [options]

Options:
    --host HOST         Server host address (default: 0.0.0.0)
    --port PORT         Server port (default: 631)
    --log-level LEVEL   Logging level (default: INFO)
    --log-file PATH     Log file path (default: console only)
    --config PATH       Configuration file path
    --no-mdns           Disable mDNS service announcement
    --debug             Enable debug mode
    --help              Show this help message

Environment Variables:
    PRINTSERVER_HOST    Server host address
    PRINTSERVER_PORT    Server port
    PRINTER_NAME        Printer name for mDNS
    LOG_LEVEL          Logging level
"""

import asyncio
import argparse
import sys
import os
import signal
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Fix relative imports by importing config first
import config.settings as config_module
settings = config_module.settings

# Import server components
import server.ipp_server as ipp_server_module
import server.printer_backend as printer_backend_module  
import server.converter as converter_module
import server.mdns_announcer as mdns_module
import server.utils as utils_module

IPPServer = ipp_server_module.IPPServer
create_printer_backend = printer_backend_module.create_printer_backend
DocumentConverter = converter_module.DocumentConverter
create_mdns_announcer = mdns_module.create_mdns_announcer

# Import utility functions
setup_logging = utils_module.setup_logging
validate_configuration = utils_module.validate_configuration
get_system_info = utils_module.get_system_info
create_status_report = utils_module.create_status_report
SignalHandler = utils_module.SignalHandler
health_check = utils_module.health_check
check_dependencies = utils_module.check_dependencies

import logging
logger = logging.getLogger(__name__)

class PrintServer:
    """
    Main print server application
    
    Coordinates all server components: IPP HTTP server, mDNS announcer,
    printer backend, and document converter.
    """
    
    def __init__(self, args):
        """
        Initialize print server
        
        Args:
            args: Parsed command line arguments
        """
        self.args = args
        self.ipp_server = None
        self.mdns_announcer = None
        self.printer_backend = None
        self.converter = None
        self.signal_handler = SignalHandler()
        
        # Override settings from command line arguments
        if args.host:
            settings.SERVER_HOST = args.host
        if args.port:
            settings.SERVER_PORT = args.port
    
    async def start(self):
        """Start all server components"""
        logger.info(f"Starting {settings.PRINTER_NAME} IPP Print Server v{settings.VERSION}")
        
        try:
            # Setup signal handling
            self.signal_handler.setup_signal_handlers()
            self.signal_handler.add_shutdown_callback(self.stop)
            
            # Validate configuration
            if not validate_configuration():
                logger.error("Configuration validation failed, exiting")
                sys.exit(1)
            
            # Show system information
            if self.args.debug:
                system_info = get_system_info()
                logger.debug(f"System information:\n{system_info}")
                
                deps = check_dependencies()
                logger.debug(f"Dependencies: {deps}")
            
            # Initialize components
            await self._initialize_components()
            
            # Start services
            await self._start_services()
            
            logger.info("Print server started successfully")
            logger.info(f"IPP URI: {settings.get_printer_uri()}")
            logger.info(f"Web interface: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}/")
            
            # Print status report in debug mode
            if self.args.debug:
                status = create_status_report()
                logger.debug(f"Status report:\n{status}")
            
            # Wait for shutdown signal
            await self.signal_handler.wait_for_shutdown()
            
        except Exception as e:
            logger.error(f"Failed to start print server: {e}")
            if self.args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        finally:
            await self.stop()
    
    async def _initialize_components(self):
        """Initialize all server components"""
        logger.info("Initializing server components...")
        
        # Initialize printer backend
        self.printer_backend = create_printer_backend()
        logger.info(f"Created printer backend: {type(self.printer_backend).__name__}")
        
        # Try to connect to printer
        if await self.printer_backend.connect():
            printer_info = await self.printer_backend.get_printer_status()
            logger.info(f"Connected to printer: {printer_info}")
        else:
            logger.warning("Could not connect to printer - server will run in offline mode")
        
        # Initialize document converter
        self.converter = DocumentConverter()
        supported_formats = self.converter.get_supported_formats()
        logger.info(f"Document converter supports: {supported_formats}")
        
        # Initialize IPP server
        self.ipp_server = IPPServer(
            printer_backend=self.printer_backend,
            converter=self.converter
        )
        
        # Initialize mDNS announcer (if not disabled)
        if not self.args.no_mdns:
            try:
                self.mdns_announcer = create_mdns_announcer(
                    async_mode=True,
                    server_host=settings.SERVER_HOST,
                    server_port=settings.SERVER_PORT
                )
                logger.info("mDNS announcer initialized")
            except ImportError as e:
                logger.warning(f"mDNS announcer disabled: {e}")
                self.mdns_announcer = None
        else:
            logger.info("mDNS announcer disabled by user")
    
    async def _start_services(self):
        """Start all services"""
        logger.info("Starting services...")
        
        # Start IPP server
        await self.ipp_server.start(settings.SERVER_HOST, settings.SERVER_PORT)
        
        # Start mDNS announcer
        if self.mdns_announcer:
            try:
                await self.mdns_announcer.start()
                logger.info("mDNS services published")
            except Exception as e:
                logger.error(f"Failed to start mDNS announcer: {e}")
                self.mdns_announcer = None
        
        logger.info("All services started")
    
    async def stop(self):
        """Stop all server components"""
        logger.info("Stopping print server...")
        
        try:
            # Stop mDNS announcer
            if self.mdns_announcer:
                await self.mdns_announcer.stop()
                logger.info("mDNS announcer stopped")
            
            # Stop IPP server
            if self.ipp_server:
                await self.ipp_server.stop()
                logger.info("IPP server stopped")
            
            # Disconnect printer backend
            if self.printer_backend:
                await self.printer_backend.disconnect()
                logger.info("Printer backend disconnected")
            
            logger.info("Print server stopped")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="IPP Print Server for thermal printers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                              # Start with default settings
    python main.py --host 192.168.1.100        # Bind to specific IP
    python main.py --port 8631 --debug         # Use non-standard port with debug
    python main.py --no-mdns                    # Disable mDNS announcement
    python main.py --log-file server.log       # Log to file

Environment Variables:
    PRINTSERVER_HOST=0.0.0.0
    PRINTSERVER_PORT=631
    PRINTER_NAME="My Thermal Printer"
    LOG_LEVEL=INFO
        """
    )
    
    parser.add_argument('--host', 
                       help='Server host address (default: from config)')
    parser.add_argument('--port', type=int,
                       help='Server port (default: from config)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: from config)')
    parser.add_argument('--log-file',
                       help='Log file path (default: console only)')
    parser.add_argument('--config',
                       help='Configuration file path (not implemented yet)')
    parser.add_argument('--no-mdns', action='store_true',
                       help='Disable mDNS service announcement')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--version', action='version',
                       version=f'IPP Print Server v{settings.VERSION}')
    
    # Add health check command
    parser.add_argument('--health-check', action='store_true',
                       help='Perform health check and exit')
    
    # Add status command  
    parser.add_argument('--status', action='store_true',
                       help='Show status information and exit')
    
    return parser.parse_args()

async def run_health_check():
    """Run health check and exit"""
    print("IPP Print Server Health Check")
    print("=" * 40)
    
    health = await health_check()
    
    print(f"Status: {health['status'].upper()}")
    print(f"Timestamp: {health['timestamp']}")
    print()
    
    for check_name, check_result in health['checks'].items():
        status_icon = "✓" if check_result['status'] == 'pass' else "⚠" if check_result['status'] == 'warn' else "✗"
        print(f"{status_icon} {check_name}: {check_result['message']}")
    
    # Exit with appropriate code
    exit_code = 0 if health['status'] == 'healthy' else 1
    sys.exit(exit_code)

def run_status_report():
    """Run status report and exit"""
    print("IPP Print Server Status Report")
    print("=" * 40)
    
    status = create_status_report()
    
    print(f"Server: {status['server']['name']} v{status['server']['version']}")
    print(f"URI: {status['server']['uri']}")
    print(f"System: {status['system']['platform']}")
    print(f"Python: {status['system']['python_version']}")
    print()
    
    print("Configuration:")
    config = status['configuration']
    print(f"  Printer Width: {config['printer_width_mm']}mm")
    print(f"  Printer DPI: {config['printer_dpi']}")
    print(f"  Supported Formats: {', '.join(config['supported_formats'])}")
    print(f"  Supported Operations: {', '.join(config['supported_operations'])}")
    print()
    
    deps = check_dependencies()
    print(f"Dependencies: {deps['available_count']}/{deps['total_count']} available")
    for dep, available in deps['dependencies'].items():
        status_icon = "✓" if available else "✗"
        print(f"  {status_icon} {dep}")
    
    sys.exit(0)

async def main():
    """Main entry point"""
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Adjust log level for debug mode
        if args.debug:
            args.log_level = args.log_level or 'DEBUG'
        
        # Setup logging
        setup_logging(args.log_level, args.log_file)
        
        # Handle special commands
        if args.health_check:
            await run_health_check()
        
        if args.status:
            run_status_report()
        
        # Create and start print server
        server = PrintServer(args)
        await server.start()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Ensure we're running with Python 3.7+
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required")
        sys.exit(1)
    
    # Handle Windows event loop policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run main coroutine
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)