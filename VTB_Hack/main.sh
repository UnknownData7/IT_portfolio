#!/bin/bash
set -euo pipefail

# =============================================================================
# POSTGRES MIGRATION TOOL 
# Умная миграция с очередями, прогресс-баром и обработкой ошибок
# =============================================================================

# Импорт библиотек
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/logger.sh"
source "$SCRIPT_DIR/lib/config_loader.sh"
source "$SCRIPT_DIR/lib/database.sh"
source "$SCRIPT_DIR/lib/migration_core.sh"
source "$SCRIPT_DIR/lib/parallel_executor.sh"
source "$SCRIPT_DIR/lib/migration_queues.sh"
source "$SCRIPT_DIR/lib/migration_strategy.sh"
source "$SCRIPT_DIR/utils/validator.sh"
source "$SCRIPT_DIR/utils/dry_run.sh"
source "$SCRIPT_DIR/utils/error_handler.sh"
source "$SCRIPT_DIR/utils/progress.sh"
echo "import finished"

# Добавьте проверку после импортов:
check_imports() {
    local missing_files=()
    
    # Проверка основных библиотек
    local libs=("logger" "config_loader" "database" "migration_core" "migration_queues")
    for lib in "${libs[@]}"; do
        if [[ ! -f "$SCRIPT_DIR/lib/${lib}.sh" ]]; then
            missing_files+=("lib/${lib}.sh")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        log_error "Missing required files: ${missing_files[*]}"
        exit 1
    fi
}

# Вызовите после импортов:
check_imports

setup_migration() {
    log_info "Creating helper functions..."
    create_helper_functions
    
    log_info "Cleaning target database..."
    clean_target_tables
    
    return 0
}
# =============================================================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# =============================================================================
MIGRATION_START_TIME=0
CURRENT_PHASE=""

# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# =============================================================================
main() {
    local config_file="${1:-config/migrator.conf}"
    local threads="${2:-4}"
    
    # Инициализация
    initialize_migration "$config_file" "$threads"
    
    # Dry-run режим
    if [[ "$DRY_RUN" == "true" ]]; then
        dry_run_summary
        log_success "=== DRY RUN COMPLETED ==="
        return 0
    fi
    
    # Запуск миграции
    run_migration
    
    # Финальный отчет
    finalize_migration
}

# =============================================================================
# ИНИЦИАЛИЗАЦИЯ МИГРАЦИИ
# =============================================================================
initialize_migration() {
    local config_file="$1"
    local threads="$2"
    
    MIGRATION_START_TIME=$(date +%s)
    
    # Проверка зависимостей
    check_dependencies
    
    # Загрузка конфигурации
    load_config "$config_file" "$threads"
    setup_work_dirs
    
    # Начало миграции
    log_stage "=== POSTGRES MIGRATION START ==="
    log_info "Config: $(basename "$config_file")"
    log_info "Threads: $THREADS" 
    log_info "Dry-run: $DRY_RUN"
    log_info "Verbose: $VERBOSE"
    log_info "Start time: $(date -d "@$MIGRATION_START_TIME" '+%Y-%m-%d %H:%M:%S')"
    
    echo ""

    # Валидация подключений (только в реальном режиме)
    if [[ "$DRY_RUN" != "true" ]]; then
        validate_connections
    fi
}

validate_connections() {
    log_stage "VALIDATING DATABASE CONNECTIONS"
    
    if ! validate_database_connection "$SOURCE_DSN" "source"; then
        log_error "Cannot establish source database connection"
        exit 1
    fi
    
    if ! validate_database_connection "$TARGET_DSN" "target"; then
        log_error "Cannot establish target database connection" 
        exit 1
    fi
    
    log_success "Database connections validated successfully"
}

# =============================================================================
# ОСНОВНОЙ ПРОЦЕСС МИГРАЦИИ С ОЧЕРЕДЯМИ
# =============================================================================
run_migration() {
    log_stage "STARTING MIGRATION PROCESS"
    
    # Фаза 0: Предварительные настройки
    run_phase "PRE_SETUP" setup_migration
    
    # Фаза 1: Миграция схемы
    run_phase "SCHEMA" migrate_schema_phase
    
    # Фаза 2: Миграция данных
    run_phase "DATA" migrate_data_phase
    
    # Фаза 3: Пост-обработка
    run_phase "POST_PROCESSING" post_processing_phase
    
    log_success "All migration phases completed successfully"
}

run_phase() {
    local phase_name="$1"
    local phase_function="$2"
    local phase_start=$(date +%s)
    
    CURRENT_PHASE="$phase_name"
    log_stage "PHASE: $phase_name"
    
    # Выполнение фазы
    if ! $phase_function; then
        log_error "Phase $phase_name failed"
        exit 1
    fi
    
    local phase_end=$(date +%s)
    local phase_duration=$((phase_end - phase_start))
    log_success "Phase $phase_name completed in $(format_duration $phase_duration)"
    echo ""
}

# =============================================================================
# ФАЗЫ МИГРАЦИИ
# =============================================================================
setup_migration() {
    log_info "Creating helper functions..."
    create_helper_functions
    
    log_info "Setting up migration environment..."
    # Дополнительные настройки если нужны
    return 0
}

migrate_schema_phase() {
    # 1.1 Миграция ролей
    log_info "Migrating roles and globals..."
    migrate_roles
    
    # 1.2 Миграция схемы БД
    log_info "Migrating database schema..."
    migrate_schema
    
    # 1.3 Миграция структуры таблиц
    log_info "Migrating table structures..."
    run_migration_phase "SCHEMA"
    
    return 0
}

migrate_data_phase() {
    # 2.1 Основная миграция данных
    log_info "Migrating table data..."
    run_migration_phase "DATA"
    
    # 2.2 Миграция специальных данных (если нужно)
    log_info "Migrating special objects..."
    migrate_special_objects
    
    return 0
}

post_processing_phase() {
    # 3.1 Создание индексов
    log_info "Applying indexes..."
    run_migration_phase "INDEXES"
    
    # 3.2 Валидация миграции
    log_info "Validating migration..."
    validate_migration
    
    # 3.3 Статистика и аналитика
    log_info "Updating statistics..."
    update_statistics
    
    return 0
}

# =============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================
migrate_special_objects() {
    # Миграция последовательностей, представлений и т.д.
    if [[ -f "$SCRIPT_DIR/sql/sequences.sql" ]]; then
        log_info "Migrating sequences..."
        psql -d "$TARGET_DSN" -f "$SCRIPT_DIR/sql/sequences.sql" >/dev/null 2>&1 || {
            log_warn "Some sequences might already exist"
        }
    fi
    
    if [[ -f "$SCRIPT_DIR/sql/views.sql" ]]; then
        log_info "Migrating views..."
        psql -d "$TARGET_DSN" -f "$SCRIPT_DIR/sql/views.sql" >/dev/null 2>&1 || {
            log_warn "Some views might already exist"
        }
    fi
    
    return 0
}

update_statistics() {
    log_info "Updating database statistics..."
    psql -d "$TARGET_DSN" -c "ANALYZE;" >/dev/null 2>&1 || true
    return 0
}

# =============================================================================
# ФИНАЛИЗАЦИЯ МИГРАЦИИ
# =============================================================================
finalize_migration() {
    local migration_end_time=$(date +%s)
    local total_duration=$((migration_end_time - MIGRATION_START_TIME))
    
    log_stage "=== MIGRATION FINALIZATION ==="
    
    # Отчет о времени
    log_info "Start: $(date -d "@$MIGRATION_START_TIME" '+%Y-%m-%d %H:%M:%S')"
    log_info "End:   $(date -d "@$migration_end_time" '+%Y-%m-%d %H:%M:%S')"
    log_success "Total duration: $(format_duration $total_duration)"
    
    # Отчет об ошибках и предупреждениях
    if ! error_summary; then
        log_error "Migration completed with errors"
        exit 1
    fi
    
    # Финальное сообщение
    echo ""
    log_stage "=== POSTGRES MIGRATION COMPLETED SUCCESSFULLY ==="
    log_success "All phases completed without critical errors"
    log_info "Target database is ready for use"
}

format_duration() {
    local seconds=$1
    local hours=$((seconds / 3600))
    local minutes=$(( (seconds % 3600) / 60 ))
    local secs=$((seconds % 60))
    
    if [[ $hours -gt 0 ]]; then
        printf "%dh %dm %ds" $hours $minutes $secs
    elif [[ $minutes -gt 0 ]]; then
        printf "%dm %ds" $minutes $secs
    else
        printf "%ds" $secs
    fi
}

# =============================================================================
# ОБРАБОТЧИКИ СИГНАЛОВ И ЧИСТКА
# =============================================================================
cleanup_and_exit() {
    local exit_code=$?
    local signal_name="$1"
    
    log_error ""
    log_error "=== MIGRATION INTERRUPTED ==="
    log_error "Signal: $signal_name"
    log_error "Phase: $CURRENT_PHASE"
    log_error "Time elapsed: $(format_duration $(($(date +%s) - MIGRATION_START_TIME)))"
    
    # Показываем прогресс если есть
    if command -v show_table_progress &> /dev/null; then
        show_table_progress
    fi
    
    # Чистка временных файлов
    log_info "Cleaning up temporary files..."
    rm -rf "$WORK_DIR/temp"/* 2>/dev/null || true
    
    # Убиваем дочерние процессы
    log_info "Stopping child processes..."
    kill $(jobs -p) 2>/dev/null || true
    sleep 2
    kill -9 $(jobs -p) 2>/dev/null || true
    
    log_error "Migration aborted. Please check logs for details."
    exit $exit_code
}

# Регистрация обработчиков сигналов
trap 'cleanup_and_exit "INT"' INT
trap 'cleanup_and_exit "TERM"' TERM
trap 'handle_error $LINENO' ERR

# =============================================================================
# ЗАПУСК СКРИПТA
# =============================================================================

# Проверка аргументов
show_usage() {
    echo "Usage: $0 [config_file] [threads]"
    echo "  config_file  Path to configuration file (default: config/migrator.conf)"
    echo "  threads      Number of parallel threads (default: 4)"
    echo ""
    echo "Examples:"
    echo "  $0                          # Use default config with 4 threads"
    echo "  $0 config/prod.conf         # Use production config with 4 threads"  
    echo "  $0 config/prod.conf 8       # Use production config with 8 threads"
    echo "  $0 config/test.conf 1       # Use test config with 1 thread (serial)"
}

# Парсинг аргументов
if [[ "$#" -gt 0 ]]; then
    case "$1" in
        -h|--help|help)
            show_usage
            exit 0
            ;;
        -v|--version)
            echo "PostgreSQL Migration Tool v2.0"
            exit 0
            ;;
        *)
            # Продолжаем с обычными аргументами
            ;;
    esac
fi

# Запуск главной функции
main "$@"