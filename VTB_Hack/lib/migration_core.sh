#!/bin/bash

BATCH_SIZE="${BATCH_SIZE:-100000}"

migrate_table_structure() {
    local table="$1"
    
    log_info "Migrating structure: $table"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would create table $table"
        return 0
    fi
    
    local temp_file="$WORK_DIR/temp/structure_${table}.sql"
    
    pg_dump -s -d "$SOURCE_DSN" -t "$table" > "$temp_file"
    psql -d "$TARGET_DSN" -f "$temp_file" >/dev/null 2>&1 || {
        log_warn "Table $table might already exist"
    }
    
    rm -f "$temp_file"
}
migrate_table_data_copy() {
    local table="$1"
    local thread_id="$2"
    local where_clause="${3:-1=1}"
    
    log_table "[Thread $thread_id] Migrating data: $table"
    
    local temp_file="$WORK_DIR/temp/${table}_${thread_id}.csv"
    
    # ЭКСПОРТ данных
    log_info "Exporting $table data..."
    psql -d "$SOURCE_DSN" -c "\COPY (SELECT * FROM $table WHERE $where_clause) TO STDOUT WITH CSV" > "$temp_file"
    
    log_info "DEBUG: First 2 lines of $table CSV:"
    head -2 "$temp_file"
    
    log_info "DEBUG: Trying to import $table data..."
    
    # ЗАГРУЗКА с немедленной проверкой
    if psql -d "$TARGET_DSN" -c "\COPY $table FROM STDIN WITH CSV" < "$temp_file" 2>&1; then
        log_success "COPY successful for $table"
        
        # НЕМЕДЛЕННАЯ ПРОВЕРКА после загрузки
        local immediate_count=$(psql -d "$TARGET_DSN" -t -c "SELECT COUNT(*) FROM $table;" | tr -d ' ')
        log_info "DEBUG: Immediate count after COPY: $immediate_count rows"
    else
        log_error "Failed to import data for table: $table"
        return 1
    fi
    
    rm -f "$temp_file"
    log_success "[Thread $thread_id] Completed: $table"
}

# Универсальная функция для получения первичного ключа
get_primary_key_columns() {
    local table="$1"
    psql -d "$SOURCE_DSN" -t -c "
        SELECT string_agg(a.attname, ', ' ORDER BY k.ordinal_position)
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, ordinal_position) 
            ON k.attnum = a.attnum
        WHERE c.contype = 'p' 
          AND t.relname = '$table' 
          AND n.nspname = 'public'
        GROUP BY c.conname
        LIMIT 1;
    " | tr -d ' ' | grep -v '^$'
}

# Универсальная функция для получения всех колонок
get_table_columns() {
    local table="$1"
    psql -d "$SOURCE_DSN" -t -c "
        SELECT string_agg(column_name, ', ' ORDER BY ordinal_position)
        FROM information_schema.columns 
        WHERE table_name = '$table' 
        AND table_schema = 'public';
    " | tr -d ' ' | grep -v '^$'
}