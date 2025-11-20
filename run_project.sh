#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Онлайн-касса ВТБ launcher ==="

cd "$(dirname "$0")"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    printf "${RED}[ERROR] Python 3 не найден. Установите Python 3.12+ и попробуйте снова.${NC}\n"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    printf "${YELLOW}[WARNING] Рекомендуется Python 3.12 или выше. Текущая версия: $PYTHON_VERSION${NC}\n"
fi

if [ ! -f "venv/bin/python" ]; then
    echo "Создание виртуального окружения..."
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        printf "${RED}[ERROR] Не удалось создать виртуальное окружение.${NC}\n"
        exit 1
    fi
fi

. venv/bin/activate
if [ $? -ne 0 ]; then
    printf "${RED}[ERROR] Не удалось активировать виртуальное окружение.${NC}\n"
    exit 1
fi

read -p "Установить/обновить зависимости (pip install -r requirements.txt)? [y/N]: " INSTALL_DEPS
if [ "$INSTALL_DEPS" = "y" ] || [ "$INSTALL_DEPS" = "Y" ]; then
    echo "Установка зависимостей..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        printf "${RED}[ERROR] Не удалось установить зависимости.${NC}\n"
        deactivate
        exit 1
    fi

    if [ -f "requirements-dev.txt" ]; then
        read -p "Установить dev-зависимости (pip install -r requirements-dev.txt)? [y/N]: " INSTALL_DEV
        if [ "$INSTALL_DEV" = "y" ] || [ "$INSTALL_DEV" = "Y" ]; then
            echo "Установка dev-зависимостей..."
            pip install -r requirements-dev.txt
            if [ $? -ne 0 ]; then
                printf "${RED}[ERROR] Не удалось установить dev-зависимости.${NC}\n"
                deactivate
                exit 1
            fi
        fi
    fi
fi

read -p "Применить миграции базы данных (python manage.py migrate)? [y/N]: " RUN_MIGRATIONS
if [ "$RUN_MIGRATIONS" = "y" ] || [ "$RUN_MIGRATIONS" = "Y" ]; then
    echo "Применение миграций..."
    python manage.py migrate
    if [ $? -ne 0 ]; then
        printf "${RED}[ERROR] Миграции не применены.${NC}\n"
        deactivate
        exit 1
    fi
fi

read -p "Загрузить тестовые данные (python manage.py load_test_data)? [y/N]: " LOAD_FIXTURES
if [ "$LOAD_FIXTURES" = "y" ] || [ "$LOAD_FIXTURES" = "Y" ]; then
    echo "Загрузка тестовых данных..."
    python manage.py load_test_data
    if [ $? -ne 0 ]; then
        printf "${RED}[ERROR] Не удалось загрузить тестовые данные.${NC}\n"
        deactivate
        exit 1
    fi
fi

read -p "Запустить тесты (python manage.py test banking)? [y/N]: " RUN_TESTS
if [ "$RUN_TESTS" = "y" ] || [ "$RUN_TESTS" = "Y" ]; then
    echo "Запуск тестов..."
    python manage.py test banking
    if [ $? -ne 0 ]; then
        printf "${YELLOW}[WARNING] Некоторые тесты не прошли. Продолжить запуск сервера?${NC}\n"
        read -p "Продолжить? [y/N]: " CONTINUE
        if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
            printf "${RED}Запуск отменен.${NC}\n"
            deactivate
            exit 1
        fi
    else
        printf "${GREEN}Все тесты прошли успешно!${NC}\n"
    fi
fi

printf "${GREEN}Запуск сервера разработки на http://127.0.0.1:8000/ ...${NC}\n"
python manage.py runserver

deactivate

