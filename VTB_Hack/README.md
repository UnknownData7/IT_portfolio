# 🚀 Universal PostgreSQL Migration Tool

Профессиональный инструмент для миграции данных между PostgreSQL базами с поддержкой различных стратегий и автоматическим анализом зависимостей.

## ✨ Особенности

- **🔧 Универсальный** - работает с любыми таблицами PostgreSQL
- **⚡ Параллельный** - многопоточная миграция с прогресс-баром  
- **🔄 Четыре режима** - full, upsert, incremental, append
- **🔍 Автоматический анализ зависимостей** - топологическая сортировка по foreign keys
- **✅ Валидация** - автоматическая проверка результатов миграции
- **📊 Мониторинг** - детальное логирование и прогресс-бар
- **🛡️ Надежный** - обработка ошибок, транзакции, откат

## 🏗️ Архитектура

```

migration-tool/
├── main.sh                          # Главный скрипт
├── config/
│   ├── migrator.conf               # Основной конфиг
│   ├── full.conf                   # Полная миграция
│   ├── upsert.conf                 # UPSERT режим
│   ├── incremental.conf            # Инкрементальная
│   └── append.conf                 # Добавление данных
├── lib/
│   ├── logger.sh                   # Логирование
│   ├── config_loader.sh            # Загрузка конфигов
│   ├── database.sh                 # Функции БД
│   ├── migration_core.sh           # Ядро миграции
│   ├── migration_strategy.sh       # Стратегии миграции
│   ├── parallel_executor.sh        # Параллельное выполнение
│   └── migration_queues.sh         # Управление очередями
├── utils/
│   ├── error_handler.sh            # Обработка ошибок
│   ├── progress.sh                 # Прогресс-бар
│   ├── validator.sh                # Валидация
│   ├── dry_run.sh                  # Тестовый режим
│   └── check_target.sh             # Проверка результатов
└── samples/
├── sample_data.sql             # Тестовые данные
└── additional_data.sql         # Дополнительные данные

```

## 🚀 Быстрый старт

### 1. Настройка окружения

```bash
# Запуск тестовых баз данных
docker-compose up -d

# Проверка подключений
psql -d "postgresql://migrator:securepass@localhost:25432/source_db" -c "SELECT 1;"
psql -d "postgresql://migrator:securepass@localhost:25433/target_db" -c "SELECT 1;"
```

2. Загрузка тестовых данных

```bash
psql -d "postgresql://migrator:securepass@localhost:25432/source_db" -f samples/sample_data.sql
```

3. Запуск миграции

```bash
# Полная миграция
./main.sh config/full.conf 4

# UPSERT миграция  
./main.sh config/upsert.conf 4

# Инкрементальная миграция
./main.sh config/incremental.conf 4

# Простое добавление
./main.sh config/append.conf 4
```

⚙️ Конфигурация

Основные параметры (config/migrator.conf)

```bash
SOURCE_DSN="postgresql://user:pass@host:port/source_db"
TARGET_DSN="postgresql://user:pass@host:port/target_db"

# Режимы: full, upsert, incremental, append
MIGRATION_MODE="upsert"

# Таблицы для миграции (all для всех таблиц)
TABLES="users,products,orders"

# Параметры выполнения
DRY_RUN="false"
VERBOSE="true"
THREADS=4
BATCH_SIZE=10000

# Настройки incremental миграции
INCREMENTAL_COLUMN="updated_at"
LAST_MIGRATION_TIMESTAMP=""

# Условия WHERE для каждой таблицы
declare -A WHERE_CLAUSES
WHERE_CLAUSES=(
    ["users"]="status = 'active'"
    ["orders"]="created_at > '2024-01-01'"
)
```

🎯 Режимы миграции

1. FULL (Полная миграция)

· Очищает целевые таблицы
· Загружает все данные заново
· Идеально для первоначальной миграции

2. UPSERT (Обновление + вставка)

· Обновляет существующие записи
· Добавляет новые записи
· Использует ON CONFLICT для обработки дубликатов

3. INCREMENTAL (Инкрементальная)

· Мигрирует только измененные данные
· Использует временные метки (updated_at, created_at)
· Эффективно для больших баз данных

4. APPEND (Добавление)

· Просто добавляет данные в конец
· Могут возникать дубликаты
· Быстрый для добавления новых данных

🔧 Расширенные возможности

Автоматический анализ зависимостей

Скрипт автоматически определяет foreign key зависимости и загружает таблицы в правильном порядке:

```bash
# Пример порядка загрузки
products → users → orders
```

Параллельная миграция

· До 8 параллельных потоков
· Прогресс-бар с детальной статистикой
· Балансировка нагрузки между потоками

Валидация результатов

```bash
# Проверка результатов миграции
./utils/check_target.sh          # Полная проверка
./utils/check_target.sh quick    # Быстрая проверка
./utils/check_target.sh structure # Проверка структур
```

🐛 Отладка и мониторинг

Dry-run режим

```bash
# Тестовый запуск без реальной миграции
DRY_RUN="true" ./main.sh config/migrator.conf 2
```

Детальное логирование

```bash
# Включение verbose режима
VERBOSE="true" ./main.sh config/migrator.conf 2
```

Проверка зависимостей

```bash
# Анализ порядка загрузки таблиц
psql -d "$SOURCE_DSN" -c "
SELECT conname, contype, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'orders'::regclass;"
```

📊 Производительность

· 3 таблицы, 9 записей: ~5 секунд
· Автоматическая балансировка нагрузки
· Оптимальное использование потоков
· Минимальные блокировки БД

🛠️ Технические детали

Поддерживаемые версии PostgreSQL

· PostgreSQL 12+
· Все современные дистрибутивы Linux
· Поддержка Docker и standalone

Требования

· Bash 4.0+
· PostgreSQL client tools (psql, pg_dump)
· Доступ к source и target базам данных

🤝 Разработка

Добавление новой функциональности

1. Создайте модуль в lib/
2. Добавьте импорт в main.sh
3. Протестируйте на тестовых данных
4. Обновите документацию

Тестирование

```bash
# Запуск всех тестов
./test_all_modes.sh

# Тестирование конкретного режима
./main.sh config/upsert.conf 2 && ./utils/check_target.sh
```

📝 Лицензия

MIT License - свободное использование и модификация.

🎉 Благодарности

Разработано в ходе интенсивной сессии разработки с глубоким анализом проблем миграции и созданием универсального решения для PostgreSQL.

---

🚀 Ваш универсальный инструмент миграции PostgreSQL готов к использованию в production!

```
