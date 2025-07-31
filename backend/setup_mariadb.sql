-- Создание базы данных
CREATE DATABASE IF NOT EXISTS vrachiapp_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Создание пользователя
CREATE USER IF NOT EXISTS 'vrachiapp_user'@'localhost' IDENTIFIED BY 'vrachiapp_password';

-- Предоставление прав пользователю
GRANT ALL PRIVILEGES ON vrachiapp_db.* TO 'vrachiapp_user'@'localhost';

-- Применение изменений
FLUSH PRIVILEGES;

-- Выбор базы данных
USE vrachiapp_db;

-- Показать созданные объекты
SHOW DATABASES;
SHOW GRANTS FOR 'vrachiapp_user'@'localhost'; 