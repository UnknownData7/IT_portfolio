#!/bin/bash

PARALLEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PARALLEL_DIR/../utils/progress.sh"
source "$PARALLEL_DIR/../utils/error_handler.sh"

PROGRESS_TOTAL=0
PROGRESS_CURRENT=0
declare -A TABLE_PROGRESS

# Функция для получения таблиц, на которые ссылается указанная таблица
get_referenced_tables() {
    local table="$1"
    psql -d "$SOURCE_DSN" -t -c "
        SELECT DISTINCT confrelid::regclass::text
        FROM pg_constraint 
        WHERE conrelid = '$table'::regclass 
        AND contype = 'f'
        AND confrelid != conrelid;
    " | tr -d ' ' | grep -v '^$'
}

# Функция для топологической сортировки таблиц
sort_tables_by_dependencies() {
    local tables=("$@")
    local sorted=()
    local visited=()
    
    # Рекурсивная функция обхода
    visit() {
        local table="$1"
        
        # Если уже посещали - выходим
        if [[ " ${visited[@]} " =~ " $table " ]]; then
            return
        fi
        
        visited+=("$table")
        
        # Получаем таблицы, на которые ссылается текущая
        local referenced_tables=($(get_referenced_tables "$table"))
        
        # Сначала посещаем зависимости
        for ref_table in "${referenced_tables[@]}"; do
            # Проверяем что зависимость есть в нашем списке миграции
            if [[ " ${tables[@]} " =~ " $ref_table " ]]; then
                visit "$ref_table"
            fi
        done
        
        # Добавляем текущую таблицу после зависимостей
        sorted+=("$table")
    }
    
    # Обходим все таблицы
    for table in "${tables[@]}"; do
        visit "$table"
    done
    
    echo "${sorted[@]}"
}

parallel_migrate_tables() {
    local tables=($(get_tables_to_migrate))
    local table_count=${#tables[@]}
    
    log_stage "PARALLEL TABLE MIGRATION - MODE: $MIGRATION_MODE"
    log_info "Migrating $table_count tables using $THREADS threads"
    
    # Топологическая сортировка таблиц по зависимостям
    local sorted_tables=($(sort_tables_by_dependencies "${tables[@]}"))
    
    log_info "Topological order: ${sorted_tables[*]}"
    
    # Логируем зависимости для отладки
    for table in "${sorted_tables[@]}"; do
        local deps=($(get_referenced_tables "$table"))
        if [[ ${#deps[@]} -gt 0 ]]; then
            log_info "Table $table depends on: ${deps[*]}"
        fi
    done
    
    init_progress "$table_count"
    update_progress 0 "$table_count"
    
    local current=0
    local pids=()
    
    for table in "${sorted_tables[@]}"; do
        current=$((current + 1))
        
        # Мигрируем структуру
        if ! migrate_table_structure "$table"; then
            log_warning "Failed to migrate structure for: $table"
            update_progress "$current" "$table_count" "$table"
            continue
        fi
        
        # Запускаем миграцию данных
        migrate_table_with_strategy "$table" "$current" &
        local pid=$!
        pids+=("$pid")
        
        log_info "Started: $table (PID: $pid)"
        
        # Ограничиваем количество параллельных процессов
        if [[ ${#pids[@]} -ge $THREADS ]]; then
            wait_for_processes "${pids[@]}"
            pids=()
        fi
        
        update_progress "$current" "$table_count" "$table"
    done
    
    # Ждем завершения оставшихся процессов
    wait_for_processes "${pids[@]}"
    
    update_progress "$table_count" "$table_count"
    show_table_progress
}

# Функция для ожидания завершения процессов
wait_for_processes() {
    local pids=("$@")
    
    for pid in "${pids[@]}"; do
        if wait "$pid"; then
            log_info "Process $pid completed successfully"
        else
            log_warning "Process $pid completed with errors"
        fi
    done
}