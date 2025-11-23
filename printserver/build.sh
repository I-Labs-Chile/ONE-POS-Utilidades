#!/bin/bash
"""
Build script for IPP Print Server

This script builds the IPP Print Server for different platforms using PyInstaller.
Supports Windows, Linux, and macOS builds with appropriate optimizations.
"""

set -e  # Exit on error

# Configuration
APP_NAME="printserver"
VERSION="1.0.0"
BUILD_DIR="dist"
DIST_DIR="dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

# Function to check dependencies
check_dependencies() {
    log_info "Checking build dependencies..."
    
    # Check Python
    if ! command_exists python3 && ! command_exists python; then
        log_error "Python not found. Please install Python 3.7+"
        exit 1
    fi
    
    # Get Python executable
    PYTHON_CMD="python3"
    if ! command_exists python3; then
        PYTHON_CMD="python"
    fi
    
    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    log_info "Using Python $PYTHON_VERSION"
    
    # Check if virtual environment is recommended
    if [[ ! -d "venv" ]] && [[ ! "$VIRTUAL_ENV" ]]; then
        log_warning "No virtual environment detected. Consider using one for cleaner builds."
    fi
    
    # Check PyInstaller
    if ! $PYTHON_CMD -c "import PyInstaller" 2>/dev/null; then
        log_warning "PyInstaller not found. Installing..."
        $PYTHON_CMD -m pip install pyinstaller
    fi
}

# Function to install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."
    
    if [[ -f "requirements.txt" ]]; then
        $PYTHON_CMD -m pip install -r requirements.txt
    else
        log_error "requirements.txt not found"
        exit 1
    fi
}

# Function to clean build directories
clean_build() {
    log_info "Cleaning previous builds..."
    
    rm -rf build/
    rm -rf dist/
    rm -rf __pycache__/
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
}

# Function to build application
build_app() {
    local platform=$1
    local build_type=${2:-"onefile"}  # onefile or onedir
    
    log_info "Building IPP Print Server for $platform ($build_type)..."
    
    # PyInstaller options
    PYINSTALLER_OPTS=(
        --clean
        --noconfirm
        --log-level=INFO
    )
    
    # Build type options
    if [[ "$build_type" == "onefile" ]]; then
        PYINSTALLER_OPTS+=(--onefile)
    else
        PYINSTALLER_OPTS+=(--onedir)
    fi
    
    # Platform-specific options
    case "$platform" in
        "windows")
            PYINSTALLER_OPTS+=(
                --console
                --name="${APP_NAME}.exe"
            )
            ;;
        "linux")
            PYINSTALLER_OPTS+=(
                --console
                --name="$APP_NAME"
            )
            ;;
        "macos")
            PYINSTALLER_OPTS+=(
                --console
                --name="$APP_NAME"
                # Uncomment for .app bundle:
                # --windowed
                # --osx-bundle-identifier=com.ippserver.printserver
            )
            ;;
    esac
    
    # Use spec file if available, otherwise build from main.py
    if [[ -f "build.spec" ]]; then
        log_info "Using build.spec configuration..."
        $PYTHON_CMD -m PyInstaller "${PYINSTALLER_OPTS[@]}" build.spec
    else
        log_info "Building from main.py..."
        PYINSTALLER_OPTS+=(
            --add-data="config:config"
            --hidden-import=aiohttp
            --hidden-import=zeroconf
            --hidden-import=usb.core
            --hidden-import=PIL
            main.py
        )
        $PYTHON_CMD -m PyInstaller "${PYINSTALLER_OPTS[@]}"
    fi
}

# Function to test built application
test_build() {
    local platform=$1
    
    log_info "Testing built application..."
    
    # Find executable
    local exe_name="$APP_NAME"
    if [[ "$platform" == "windows" ]]; then
        exe_name="$APP_NAME.exe"
    fi
    
    local exe_path
    if [[ -f "dist/$exe_name" ]]; then
        exe_path="dist/$exe_name"
    elif [[ -f "dist/$APP_NAME/$exe_name" ]]; then
        exe_path="dist/$APP_NAME/$exe_name"
    else
        log_error "Built executable not found"
        return 1
    fi
    
    log_info "Testing: $exe_path"
    
    # Test version
    if "$exe_path" --version; then
        log_success "Version test passed"
    else
        log_warning "Version test failed"
    fi
    
    # Test help
    if "$exe_path" --help >/dev/null; then
        log_success "Help test passed"
    else
        log_warning "Help test failed"
    fi
    
    # Test health check
    if "$exe_path" --health-check; then
        log_success "Health check passed"
    else
        log_warning "Health check failed (expected if no printer connected)"
    fi
}

# Function to create distribution package
create_package() {
    local platform=$1
    local version=$2
    
    log_info "Creating distribution package for $platform..."
    
    local package_name="${APP_NAME}-${version}-${platform}"
    local package_dir="$DIST_DIR/$package_name"
    
    # Create package directory
    mkdir -p "$package_dir"
    
    # Copy executable
    if [[ -f "dist/$APP_NAME" ]]; then
        cp "dist/$APP_NAME" "$package_dir/"
    elif [[ -f "dist/$APP_NAME.exe" ]]; then
        cp "dist/$APP_NAME.exe" "$package_dir/"
    elif [[ -d "dist/$APP_NAME" ]]; then
        cp -r "dist/$APP_NAME"/* "$package_dir/"
    fi
    
    # Copy documentation
    [[ -f "README.md" ]] && cp "README.md" "$package_dir/"
    [[ -f "LICENSE" ]] && cp "LICENSE" "$package_dir/"
    
    # Create startup scripts
    case "$platform" in
        "windows")
            cat > "$package_dir/start-server.bat" << 'EOF'
@echo off
echo Starting IPP Print Server...
printserver.exe
pause
EOF
            ;;
        "linux"|"macos")
            cat > "$package_dir/start-server.sh" << 'EOF'
#!/bin/bash
echo "Starting IPP Print Server..."
./printserver "$@"
EOF
            chmod +x "$package_dir/start-server.sh"
            ;;
    esac
    
    # Create archive
    case "$platform" in
        "windows")
            if command_exists zip; then
                (cd "$DIST_DIR" && zip -r "${package_name}.zip" "$package_name")
                log_success "Created: $DIST_DIR/${package_name}.zip"
            fi
            ;;
        "linux"|"macos")
            if command_exists tar; then
                (cd "$DIST_DIR" && tar -czf "${package_name}.tar.gz" "$package_name")
                log_success "Created: $DIST_DIR/${package_name}.tar.gz"
            fi
            ;;
    esac
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help              Show this help message"
    echo "  --clean             Clean build directories only"
    echo "  --deps              Install dependencies only"
    echo "  --test              Test existing build"
    echo "  --package           Create distribution package"
    echo "  --onedir            Build as one-directory (default: one-file)"
    echo "  --no-test           Skip build testing"
    echo "  --version VERSION   Set version (default: $VERSION)"
    echo ""
    echo "Examples:"
    echo "  $0                  # Full build with all steps"
    echo "  $0 --clean          # Clean build directories"
    echo "  $0 --onedir         # Build as directory instead of single file"
    echo "  $0 --version 1.2.0  # Build with specific version"
}

# Main function
main() {
    local clean_only=false
    local deps_only=false
    local test_only=false
    local package_only=false
    local build_type="onefile"
    local skip_test=false
    local version="$VERSION"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                show_usage
                exit 0
                ;;
            --clean)
                clean_only=true
                shift
                ;;
            --deps)
                deps_only=true
                shift
                ;;
            --test)
                test_only=true
                shift
                ;;
            --package)
                package_only=true
                shift
                ;;
            --onedir)
                build_type="onedir"
                shift
                ;;
            --no-test)
                skip_test=true
                shift
                ;;
            --version)
                version="$2"
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Detect platform
    local platform=$(detect_platform)
    log_info "Detected platform: $platform"
    
    # Execute requested operation
    if [[ "$clean_only" == true ]]; then
        clean_build
        log_success "Clean completed"
        exit 0
    fi
    
    if [[ "$deps_only" == true ]]; then
        check_dependencies
        install_dependencies
        log_success "Dependencies installed"
        exit 0
    fi
    
    if [[ "$test_only" == true ]]; then
        test_build "$platform"
        exit 0
    fi
    
    if [[ "$package_only" == true ]]; then
        create_package "$platform" "$version"
        exit 0
    fi
    
    # Full build process
    log_info "Starting full build process..."
    
    # Step 1: Check dependencies
    check_dependencies
    
    # Step 2: Install dependencies
    install_dependencies
    
    # Step 3: Clean previous builds
    clean_build
    
    # Step 4: Build application
    build_app "$platform" "$build_type"
    
    # Step 5: Test build (unless skipped)
    if [[ "$skip_test" != true ]]; then
        test_build "$platform" || log_warning "Some tests failed, but build continues"
    fi
    
    # Step 6: Create package
    create_package "$platform" "$version"
    
    log_success "Build completed successfully!"
    log_info "Distribution files are in: $DIST_DIR/"
}

# Run main function with all arguments
main "$@"