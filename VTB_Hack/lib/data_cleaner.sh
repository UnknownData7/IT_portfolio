#!/bin/bash

clean_target_tables() {
    local tables=($(get_tables_to_migrate))
    
    log_info "Cleaning target tables before migration..."
    
    for table in "${tables[@]}"; do
        log_info "Cleaning table: $table"
        psql -d "$TARGET_DSN" -c "TRUNCATE TABLE $table CASCADE;" 2>/dev/null || {
            log_warn "Could not truncate $table (might not exist or have dependencies)"
        }
    done
    
    log_success "Target tables cleaned"
}

# Или альтернатива - удаление только конфликтующих записей
clean_conflicting_data() {
    local table="$1"
    local temp_file="$2"
    
    log_info "Cleaning conflicting data for: $table"
    
    # Создаем временную таблицу с новыми данными
    psql -d "$TARGET_DSN" -c "
        CREATE TEMP TABLE new_data AS SELECT * FROM $table WHERE 1=0;
        \copy new_data FROM '$temp_file' WITH CSV;
        
        -- Удаляем конфликтующие записи
        DELETE FROM $table 
        WHERE id IN (SELECT id FROM new_data);
        
        DROP TABLE new_data;
    " >/dev/null 2>&1 || true
}