#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏥 Запуск Healzy Backend...${NC}"

# Проверяем, активировано ли виртуальное окружение
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️  Виртуальное окружение не активировано${NC}"
    
    # Проверяем наличие .venv
    if [ -d ".venv" ]; then
        echo -e "${BLUE}📦 Активируем виртуальное окружение...${NC}"
        source .venv/bin/activate
    else
        echo -e "${YELLOW}📦 Создаем виртуальное окружение...${NC}"
        python -m venv .venv
        source .venv/bin/activate
    fi
else
    echo -e "${GREEN}✅ Виртуальное окружение активировано${NC}"
fi

# Проверяем установлен ли Django
if ! python -c "import django" 2>/dev/null; then
    echo -e "${YELLOW}📦 Устанавливаем зависимости...${NC}"
    
    # Устанавливаем зависимости
    pip install Django==4.2.23
    pip install djangorestframework==3.14.0
    pip install django-cors-headers==4.3.1
    pip install requests==2.31.0
    pip install google-auth==2.23.4
    pip install google-auth-oauthlib==1.1.0
    pip install python-decouple==3.8
    
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
else
    echo -e "${GREEN}✅ Django уже установлен${NC}"
fi

# Проверяем настройки базы данных
echo -e "${BLUE}🗄️  Проверяем настройки базы данных...${NC}"

# Временно переключаемся на SQLite для простоты
if grep -q "mysql" vrachiapp_backend/settings.py; then
    echo -e "${YELLOW}⚠️  Переключаемся на SQLite для разработки${NC}"
    
    # Создаем резервную копию
    cp vrachiapp_backend/settings.py vrachiapp_backend/settings.py.backup
    
    # Заменяем настройки базы данных
    sed -i 's/ENGINE.*mysql/ENGINE.*sqlite3/' vrachiapp_backend/settings.py
    sed -i 's/NAME.*vrachiapp_db/NAME.*BASE_DIR \/ "db.sqlite3"/' vrachiapp_backend/settings.py
    sed -i '/USER.*PASSWORD.*HOST.*PORT.*OPTIONS/d' vrachiapp_backend/settings.py
fi

# Применяем миграции
echo -e "${BLUE}🔄 Применяем миграции...${NC}"
python manage.py makemigrations
python manage.py migrate

# Проверяем наличие суперпользователя
echo -e "${BLUE}👤 Проверяем суперпользователя...${NC}"
if ! python manage.py shell -c "from django.contrib.auth.models import User; print('Superuser exists' if User.objects.filter(is_superuser=True).exists() else 'No superuser')" 2>/dev/null | grep -q "Superuser exists"; then
    echo -e "${YELLOW}⚠️  Создайте суперпользователя:${NC}"
    echo -e "${BLUE}   python manage.py createsuperuser${NC}"
fi

echo -e "${GREEN}🚀 Запускаем Django сервер...${NC}"
echo -e "${BLUE}📍 Сервер будет доступен по адресу: http://localhost:8000${NC}"
echo -e "${BLUE}📍 API endpoints: http://localhost:8000/api/auth/${NC}"
echo -e "${BLUE}📍 Django Admin: http://localhost:8000/admin/${NC}"
echo -e "${YELLOW}💡 Для остановки сервера нажмите Ctrl+C${NC}"
echo ""

# Запускаем сервер
python manage.py runserver 