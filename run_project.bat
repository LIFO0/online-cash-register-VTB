@echo off
chcp 65001
setlocal enabledelayedexpansion

pushd "%~dp0"

echo === Онлайн-касса ВТБ launcher ===

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not in PATH. Install Python 3.12+ and try again.
    goto :end
)

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :end
    )
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    goto :end
)

set /p INSTALL_DEPS="Install/update dependencies (pip install -r requirements.txt)? [y/N]: "
if /i "!INSTALL_DEPS!"=="Y" (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        goto :deactivate
    )

    if exist "requirements-dev.txt" (
        set /p INSTALL_DEV="Install dev dependencies (pip install -r requirements-dev.txt)? [y/N]: "
        if /i "!INSTALL_DEV!"=="Y" (
            echo Installing dev dependencies...
            pip install -r requirements-dev.txt
            if errorlevel 1 (
                echo [ERROR] Dev dependency installation failed.
                goto :deactivate
            )
        )
    )
)

set /p RUN_MIGRATIONS="Run database migrations (python manage.py migrate)? [y/N]: "
if /i "!RUN_MIGRATIONS!"=="Y" (
    echo Applying migrations...
    python manage.py migrate
    if errorlevel 1 (
        echo [ERROR] Migrations failed.
        goto :deactivate
    )
)

set /p LOAD_FIXTURES="Load test data (python manage.py load_test_data)? [y/N]: "
if /i "!LOAD_FIXTURES!"=="Y" (
    echo Loading test data...
    python manage.py load_test_data
    if errorlevel 1 (
        echo [ERROR] Loading test data failed.
        goto :deactivate
    )
)

set /p RUN_TESTS="Run tests (python manage.py test banking)? [y/N]: "
if /i "!RUN_TESTS!"=="Y" (
    echo Running tests...
    python manage.py test banking
    if errorlevel 1 (
        echo [WARNING] Some tests failed. Continue with server startup?
        set /p CONTINUE="Continue? [y/N]: "
        if /i not "!CONTINUE!"=="Y" (
            echo Startup cancelled.
            goto :deactivate
        )
    ) else (
        echo All tests passed successfully!
    )
)

echo Starting development server on http://127.0.0.1:8000/ ...
python manage.py runserver

:deactivate
call deactivate

:end
popd
echo Done.

