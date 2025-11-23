@echo off
setlocal enabledelayedexpansion

REM Try to set UTF-8 encoding (may fail on older Windows versions)
chcp 65001 >nul 2>&1

REM Change to script directory
pushd "%~dp0"

echo === Онлайн-касса ВТБ launcher ===
echo.

REM Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден в PATH.
    echo Установите Python 3.12+ и добавьте его в PATH, затем попробуйте снова.
    goto :end
)

REM Check Python version
echo Проверка версии Python...
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Найдена версия Python: !PYTHON_VERSION!

REM Extract major and minor version numbers
for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set MAJOR=%%a
    set MINOR=%%b
)

REM Check if version is 3.12 or higher
if !MAJOR! LSS 3 (
    echo [ERROR] Требуется Python 3.12 или выше. Текущая версия: !PYTHON_VERSION!
    goto :end
)
if !MAJOR! EQU 3 (
    if !MINOR! LSS 12 (
        echo [WARNING] Рекомендуется Python 3.12 или выше. Текущая версия: !PYTHON_VERSION!
        echo Продолжить? [y/N]:
        set /p CONTINUE_VERSION=
        if /i not "!CONTINUE_VERSION!"=="Y" (
            echo Запуск отменен.
            goto :end
        )
    )
)

REM Check if manage.py exists
if not exist "manage.py" (
    echo [ERROR] Файл manage.py не найден. Убедитесь, что вы запускаете скрипт из корневой директории проекта.
    goto :end
)

REM Create virtual environment if it doesn't exist
if not exist "venv\Scripts\python.exe" (
    echo Создание виртуального окружения...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Не удалось создать виртуальное окружение.
        echo Убедитесь, что у вас установлен Python и есть права на запись в текущую директорию.
        goto :end
    )
    echo Виртуальное окружение создано успешно.
) else (
    echo Виртуальное окружение уже существует.
)

REM Activate virtual environment
echo Активация виртуального окружения...
call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Не удалось активировать виртуальное окружение.
    echo Попробуйте удалить папку venv и запустить скрипт снова.
    goto :end
)

REM Verify pip is available
where pip >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip не найден в виртуальном окружении.
    echo Попробуйте пересоздать виртуальное окружение.
    goto :deactivate
)

REM Check if requirements.txt exists before asking
if not exist "requirements.txt" (
    echo [WARNING] Файл requirements.txt не найден. Пропуск установки зависимостей.
    set INSTALL_DEPS=N
) else (
    set /p INSTALL_DEPS="Установить/обновить зависимости (pip install -r requirements.txt)? [y/N]: "
)

if /i "!INSTALL_DEPS!"=="Y" (
    echo Установка зависимостей...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Не удалось установить зависимости.
        echo Проверьте подключение к интернету и доступность PyPI.
        goto :deactivate
    )
    echo Зависимости установлены успешно.

    if exist "requirements-dev.txt" (
        set /p INSTALL_DEV="Установить dev зависимости (pip install -r requirements-dev.txt)? [y/N]: "
        if /i "!INSTALL_DEV!"=="Y" (
            echo Установка dev зависимостей...
            pip install -r requirements-dev.txt
            if errorlevel 1 (
                echo [ERROR] Не удалось установить dev зависимости.
                goto :deactivate
            )
            echo Dev зависимости установлены успешно.
        )
    )
)

REM Run migrations
set /p RUN_MIGRATIONS="Применить миграции базы данных (python manage.py migrate)? [y/N]: "
if /i "!RUN_MIGRATIONS!"=="Y" (
    echo Применение миграций...
    python manage.py migrate
    if errorlevel 1 (
        echo [ERROR] Не удалось применить миграции.
        goto :deactivate
    )
    echo Миграции применены успешно.
)

REM Load test data
set /p LOAD_FIXTURES="Загрузить тестовые данные (python manage.py load_test_data)? [y/N]: "
if /i "!LOAD_FIXTURES!"=="Y" (
    echo Загрузка тестовых данных...
    python manage.py load_test_data
    if errorlevel 1 (
        echo [ERROR] Не удалось загрузить тестовые данные.
        goto :deactivate
    )
    echo Тестовые данные загружены успешно.
)

REM Run tests
set /p RUN_TESTS="Запустить тесты (python manage.py test banking)? [y/N]: "
if /i "!RUN_TESTS!"=="Y" (
    echo Запуск тестов...
    python manage.py test banking
    if errorlevel 1 (
        echo [WARNING] Некоторые тесты не прошли. Продолжить запуск сервера?
        set /p CONTINUE="Продолжить? [y/N]: "
        if /i not "!CONTINUE!"=="Y" (
            echo Запуск отменен.
            goto :deactivate
        )
    ) else (
        echo Все тесты прошли успешно!
    )
)

REM Start development server
echo.
echo Запуск сервера разработки на http://127.0.0.1:8000/ ...
echo Для остановки нажмите Ctrl+C
echo.
python manage.py runserver
if errorlevel 1 (
    echo [ERROR] Не удалось запустить сервер.
    echo Убедитесь, что порт 8000 свободен или используйте другой порт.
)

:deactivate
REM Only deactivate if we're in a virtual environment
if defined VIRTUAL_ENV (
    call deactivate >nul 2>&1
)

:end
popd
echo.
echo Готово.
pause

