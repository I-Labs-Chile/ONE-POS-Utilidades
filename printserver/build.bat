@echo off
REM Build script for IPP Print Server on Windows
REM This script builds the IPP Print Server using PyInstaller

setlocal enabledelayedexpansion

REM Configuration
set APP_NAME=printserver
set VERSION=1.0.0
set BUILD_DIR=dist
set DIST_DIR=dist

REM Colors (Windows doesn't support colors in batch easily, so we use echo)
set "INFO=[INFO]"
set "SUCCESS=[SUCCESS]"  
set "WARNING=[WARNING]"
set "ERROR=[ERROR]"

REM Function to log info
:log_info
echo %INFO% %1
goto :eof

REM Function to log success
:log_success
echo %SUCCESS% %1
goto :eof

REM Function to log warning
:log_warning
echo %WARNING% %1
goto :eof

REM Function to log error
:log_error
echo %ERROR% %1
goto :eof

REM Function to check if command exists
:command_exists
where %1 >nul 2>&1
goto :eof

REM Function to check dependencies
:check_dependencies
call :log_info "Checking build dependencies..."

REM Check Python
call :command_exists python
if errorlevel 1 (
    call :command_exists py
    if errorlevel 1 (
        call :log_error "Python not found. Please install Python 3.7+"
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

REM Check Python version
for /f "tokens=2" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
call :log_info "Using Python !PYTHON_VERSION!"

REM Check PyInstaller
%PYTHON_CMD% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    call :log_warning "PyInstaller not found. Installing..."
    %PYTHON_CMD% -m pip install pyinstaller
)
goto :eof

REM Function to install dependencies
:install_dependencies
call :log_info "Installing Python dependencies..."

if exist requirements.txt (
    %PYTHON_CMD% -m pip install -r requirements.txt
) else (
    call :log_error "requirements.txt not found"
    exit /b 1
)
goto :eof

REM Function to clean build directories
:clean_build
call :log_info "Cleaning previous builds..."

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

REM Clean Python cache files
for /r %%i in (*.pyc) do del "%%i" >nul 2>&1
for /d /r %%i in (__pycache__) do rmdir /s /q "%%i" >nul 2>&1
goto :eof

REM Function to build application
:build_app
call :log_info "Building IPP Print Server for Windows..."

set BUILD_TYPE=%1
if "%BUILD_TYPE%"=="" set BUILD_TYPE=onefile

REM PyInstaller options
set PYINSTALLER_OPTS=--clean --noconfirm --log-level=INFO --console

REM Build type options
if "%BUILD_TYPE%"=="onefile" (
    set PYINSTALLER_OPTS=!PYINSTALLER_OPTS! --onefile
) else (
    set PYINSTALLER_OPTS=!PYINSTALLER_OPTS! --onedir
)

REM Windows-specific options
set PYINSTALLER_OPTS=!PYINSTALLER_OPTS! --name=%APP_NAME%.exe

REM Use spec file if available
if exist build.spec (
    call :log_info "Using build.spec configuration..."
    %PYTHON_CMD% -m PyInstaller !PYINSTALLER_OPTS! build.spec
) else (
    call :log_info "Building from main.py..."
    %PYTHON_CMD% -m PyInstaller !PYINSTALLER_OPTS! --add-data="config;config" --hidden-import=aiohttp --hidden-import=zeroconf --hidden-import=usb.core --hidden-import=PIL main.py
)

if errorlevel 1 (
    call :log_error "Build failed"
    exit /b 1
)
goto :eof

REM Function to test built application
:test_build
call :log_info "Testing built application..."

set EXE_PATH=
if exist "dist\%APP_NAME%.exe" (
    set EXE_PATH=dist\%APP_NAME%.exe
) else if exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    set EXE_PATH=dist\%APP_NAME%\%APP_NAME%.exe
) else (
    call :log_error "Built executable not found"
    exit /b 1
)

call :log_info "Testing: !EXE_PATH!"

REM Test version
"!EXE_PATH!" --version >nul
if errorlevel 1 (
    call :log_warning "Version test failed"
) else (
    call :log_success "Version test passed"
)

REM Test help
"!EXE_PATH!" --help >nul
if errorlevel 1 (
    call :log_warning "Help test failed"
) else (
    call :log_success "Help test passed"
)

REM Test health check
"!EXE_PATH!" --health-check >nul
if errorlevel 1 (
    call :log_warning "Health check failed (expected if no printer connected)"
) else (
    call :log_success "Health check passed"
)
goto :eof

REM Function to create distribution package
:create_package
set VERSION_ARG=%1
if "%VERSION_ARG%"=="" set VERSION_ARG=%VERSION%

call :log_info "Creating distribution package for Windows..."

set PACKAGE_NAME=%APP_NAME%-%VERSION_ARG%-windows
set PACKAGE_DIR=%DIST_DIR%\%PACKAGE_NAME%

REM Create package directory
if not exist "%PACKAGE_DIR%" mkdir "%PACKAGE_DIR%"

REM Copy executable
if exist "dist\%APP_NAME%.exe" (
    copy "dist\%APP_NAME%.exe" "%PACKAGE_DIR%\"
) else if exist "dist\%APP_NAME%" (
    xcopy "dist\%APP_NAME%\*" "%PACKAGE_DIR%\" /e /h /k
)

REM Copy documentation
if exist README.md copy README.md "%PACKAGE_DIR%\"
if exist LICENSE copy LICENSE "%PACKAGE_DIR%\"

REM Create startup script
echo @echo off > "%PACKAGE_DIR%\start-server.bat"
echo echo Starting IPP Print Server... >> "%PACKAGE_DIR%\start-server.bat"
echo %APP_NAME%.exe >> "%PACKAGE_DIR%\start-server.bat"
echo pause >> "%PACKAGE_DIR%\start-server.bat"

REM Create zip if possible
where zip >nul 2>&1
if not errorlevel 1 (
    cd /d %DIST_DIR%
    zip -r "%PACKAGE_NAME%.zip" "%PACKAGE_NAME%"
    cd ..
    call :log_success "Created: %DIST_DIR%\%PACKAGE_NAME%.zip"
) else (
    call :log_warning "zip command not found. Package directory created: %PACKAGE_DIR%"
)
goto :eof

REM Function to show usage
:show_usage
echo Usage: %0 [OPTIONS]
echo.
echo Options:
echo   --help              Show this help message
echo   --clean             Clean build directories only
echo   --deps              Install dependencies only
echo   --test              Test existing build
echo   --package           Create distribution package
echo   --onedir            Build as one-directory (default: one-file)
echo   --no-test           Skip build testing
echo   --version VERSION   Set version (default: %VERSION%)
echo.
echo Examples:
echo   %0                  # Full build with all steps
echo   %0 --clean          # Clean build directories
echo   %0 --onedir         # Build as directory instead of single file
echo   %0 --version 1.2.0  # Build with specific version
goto :eof

REM Main function
:main
set CLEAN_ONLY=false
set DEPS_ONLY=false
set TEST_ONLY=false
set PACKAGE_ONLY=false
set BUILD_TYPE=onefile
set SKIP_TEST=false
set VERSION_ARG=%VERSION%

REM Parse command line arguments
:parse_args
if "%1"=="" goto end_parse
if "%1"=="--help" (
    call :show_usage
    exit /b 0
)
if "%1"=="--clean" (
    set CLEAN_ONLY=true
    shift
    goto parse_args
)
if "%1"=="--deps" (
    set DEPS_ONLY=true
    shift
    goto parse_args
)
if "%1"=="--test" (
    set TEST_ONLY=true
    shift
    goto parse_args
)
if "%1"=="--package" (
    set PACKAGE_ONLY=true
    shift
    goto parse_args
)
if "%1"=="--onedir" (
    set BUILD_TYPE=onedir
    shift
    goto parse_args
)
if "%1"=="--no-test" (
    set SKIP_TEST=true
    shift
    goto parse_args
)
if "%1"=="--version" (
    set VERSION_ARG=%2
    shift
    shift
    goto parse_args
)
call :log_error "Unknown option: %1"
call :show_usage
exit /b 1

:end_parse

call :log_info "Detected platform: Windows"

REM Execute requested operation
if "%CLEAN_ONLY%"=="true" (
    call :clean_build
    call :log_success "Clean completed"
    exit /b 0
)

if "%DEPS_ONLY%"=="true" (
    call :check_dependencies
    call :install_dependencies
    call :log_success "Dependencies installed"
    exit /b 0
)

if "%TEST_ONLY%"=="true" (
    call :test_build
    exit /b 0
)

if "%PACKAGE_ONLY%"=="true" (
    call :create_package %VERSION_ARG%
    exit /b 0
)

REM Full build process
call :log_info "Starting full build process..."

REM Step 1: Check dependencies
call :check_dependencies
if errorlevel 1 exit /b 1

REM Step 2: Install dependencies
call :install_dependencies
if errorlevel 1 exit /b 1

REM Step 3: Clean previous builds
call :clean_build

REM Step 4: Build application
call :build_app %BUILD_TYPE%
if errorlevel 1 exit /b 1

REM Step 5: Test build (unless skipped)
if "%SKIP_TEST%"=="false" (
    call :test_build
)

REM Step 6: Create package
call :create_package %VERSION_ARG%

call :log_success "Build completed successfully!"
call :log_info "Distribution files are in: %DIST_DIR%\"
goto :eof

REM Entry point
call :main %*