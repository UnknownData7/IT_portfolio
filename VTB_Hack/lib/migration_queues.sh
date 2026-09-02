#!/bin/bash

run_migration_phase() {
    local phase="$1"  # SCHEMA, DATA, INDEXES
    
    case "$phase" in
        "SCHEMA")
            log_stage "MIGRATING TABLE STRUCTURES"
            migrate_all_table_structures
            ;;
        "DATA")  
            log_stage "MIGRATING TABLE DATA"
            migrate_all_table_data
            ;;
        "INDEXES")
            log_stage "APPLYING INDEXES & CONSTRAINTS"
            apply_all_indexes_and_constraints
            ;;
    esac
}

migrate_all_table_structures() {
    local tables=($(get_tables_to_migrate))
    local total_tables=${#tables[@]}
    local current=0
    
    log_info "Migrating structures for $total_tables tables..."
    
    for table in "${tables[@]}"; do
        current=$((current + 1))
        log_info "[$current/$total_tables] Creating table: $table"
        
        if ! migrate_table_structure "$table"; then
            log_warning "Failed to create table: $table"
        fi
    done
    
    log_success "Table structures migration completed"
}

migrate_all_table_data() {
    local tables=($(get_tables_to_migrate))
    
    # Используем существующий параллельный исполнитель
    parallel_migrate_tables
}

apply_all_indexes_and_constraints() {
    log_info "Applying indexes..."
    if ! apply_indexes; then
        log_warning "Some indexes failed to apply"
    fi
    
    log_info "Applying constraints..."
    if ! apply_constraints; then
        log_warning "Some constraints failed to apply"
    fi
    
    log_success "Indexes and constraints applied"
}

# Добавьте недостающие функции:
migrate_schema_phase() {
    run_migration_phase "SCHEMA"
}

migrate_data_phase() {
    run_migration_phase "DATA" 
}

setup_migration() {
    log_info "Setting up migration environment..."
    create_helper_functions
    return 0
}