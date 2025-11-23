@echo off
setlocal enabledelayedexpansion

REM Set UTF-8 encoding for proper Russian text display
chcp 65001 >nul 2>&1

REM Change to script directory
pushd "%~dp0"

echo === Online Cash Register VTB launcher ===
echo.

REM Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.12+ and add it to PATH, then try again.
    goto :end
)

REM Check Python version
echo Checking Python version...
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python version: !PYTHON_VERSION!

REM Extract major and minor version numbers
for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set MAJOR=%%a
    set MINOR=%%b
)

REM Check if version is 3.12 or higher
if !MAJOR! LSS 3 (
    echo [ERROR] Python 3.12 or higher required. Current version: !PYTHON_VERSION!
    goto :end
)
if !MAJOR! EQU 3 (
    if !MINOR! LSS 12 (
        echo [WARNING] Python 3.12+ recommended. Current version: !PYTHON_VERSION!
        echo Continue? [y/N]:
        set /p CONTINUE_VERSION=
        if /i not "!CONTINUE_VERSION!"=="Y" (
            echo Launch cancelled.
            goto :end
        )
    )
)

REM Check if manage.py exists
if not exist "manage.py" (
    echo [ERROR] manage.py not found. Make sure you run this script from project root directory.
    goto :end
)

REM Create virtual environment if it doesn't exist
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo Make sure Python is installed and you have write permissions in current directory.
        goto :end
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo Activating virtual environment...
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    echo Try deleting venv folder and run this script again.
    goto :end
)

REM Verify pip is available
where pip >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found in virtual environment.
    echo Try recreating the virtual environment.
    goto :deactivate
)

REM Check if requirements.txt exists before asking
if not exist "requirements.txt" (
    echo [WARNING] requirements.txt not found. Skipping dependency installation.
    set INSTALL_DEPS=N
) else (
    set /p INSTALL_DEPS="Install/update dependencies (pip install -r requirements.txt)? [y/N]: "
)

if /i "!INSTALL_DEPS!"=="Y" (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        echo Check your internet connection and PyPI availability.
        goto :deactivate
    )
    echo Dependencies installed successfully.

    if exist "requirements-dev.txt" (
        set /p INSTALL_DEV="Install dev dependencies (pip install -r requirements-dev.txt)? [y/N]: "
        if /i "!INSTALL_DEV!"=="Y" (
            echo Installing dev dependencies...
            pip install -r requirements-dev.txt
            if errorlevel 1 (
                echo [ERROR] Failed to install dev dependencies.
                goto :deactivate
            )
            echo Dev dependencies installed successfully.
        )
    )
)

REM Run migrations
set /p RUN_MIGRATIONS="Apply database migrations (python manage.py migrate)? [y/N]: "
if /i "!RUN_MIGRATIONS!"=="Y" (
    echo Applying migrations...
    python manage.py migrate
    if errorlevel 1 (
        echo [ERROR] Failed to apply migrations.
        goto :deactivate
    )
    echo Migrations applied successfully.
)

REM Load test data
set /p LOAD_FIXTURES="Load test data (python manage.py load_test_data)? [y/N]: "
if /i "!LOAD_FIXTURES!"=="Y" (
    echo Loading test data...
    python manage.py load_test_data
    if errorlevel 1 (
        echo [ERROR] Failed to load test data.
        goto :deactivate
    )
    echo Test data loaded successfully.
)

REM Run tests
set /p RUN_TESTS="Run tests (python manage.py test banking)? [y/N]: "
if /i "!RUN_TESTS!"=="Y" (
    echo Running tests...
    python manage.py test banking
    if errorlevel 1 (
        echo [WARNING] Some tests failed. Continue to start server?
        set /p CONTINUE="Continue? [y/N]: "
        if /i not "!CONTINUE!"=="Y" (
            echo Launch cancelled.
            goto :deactivate
        )
    ) else (
        echo All tests passed successfully!
    )
)

REM Start development server
echo.
echo Starting development server on http://127.0.0.1:8000/ ...
echo Press Ctrl+C to stop
echo.
python manage.py runserver
if errorlevel 1 (
    echo [ERROR] Failed to start server.
    echo Make sure port 8000 is free or use a different port.
)

:deactivate
REM Only deactivate if we're in a virtual environment
if defined VIRTUAL_ENV (
    call deactivate >nul 2>&1
)

:end
popd
echo.
echo Done.
pause
