#!/bin/bash

test_connection() {
    local dsn="$1"
    local dbname="$2"
    
    if ! psql "$dsn" -c "SELECT 1;" >/dev/null 2>&1; then
        log_error "Cannot connect to $dbname database"
        return 1
    fi
    log_success "Connected to $dbname database"
}

get_tables_to_migrate() {
    if [[ "$TABLES" == "all" ]]; then
        psql -d "$SOURCE_DSN" -t -c "
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        " | tr -d ' ' | grep -v '^$'
    else
        echo "$TABLES" | tr ',' '\n'
    fi
}

migrate_roles() {
    log_stage "1. MIGRATING ROLES"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would export roles"
        return 0
    fi
    
    log_info "Exporting roles..."
    if pg_dumpall --globals-only -d "$SOURCE_DSN" > "$WORK_DIR/dumps/roles.sql" 2>/dev/null; then
        log_info "Importing roles..."
        psql -d "$TARGET_DSN" -f "$WORK_DIR/dumps/roles.sql" >/dev/null 2>&1 || {
            log_warn "Some roles might already exist"
        }
        log_success "Roles migration completed"
    else
        log_warn "No roles to migrate or permission denied"
    fi
}

migrate_schema() {
    log_stage "2. MIGRATING SCHEMA"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would dump and apply schema"
        return 0
    fi
    
    log_info "Dumping schema..."
    pg_dump -s -d "$SOURCE_DSN" > "$WORK_DIR/dumps/schema.sql"
    
    log_info "Applying schema..."
    psql -d "$TARGET_DSN" -f "$WORK_DIR/dumps/schema.sql" >/dev/null 2>&1 || {
        log_warn "Some schema objects might already exist"
    }
    
    log_success "Schema migration completed"
}

create_helper_functions() {
    log_stage "3. CREATING HELPER FUNCTIONS"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would create helper functions"
        return 0
    fi
    
    log_info "Creating helper functions..."
    psql -d "$TARGET_DSN" -f "$(dirname "$0")/../sql/helper_functions.sql" >/dev/null 2>&1
    log_success "Helper functions created"
}

apply_indexes() {
    log_stage "5. APPLYING INDEXES"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would apply indexes"
        return 0
    fi
    
    if [[ -f "$(dirname "$0")/../sql/indexes.sql" ]]; then
        log_info "Applying indexes..."
        psql -d "$TARGET_DSN" -f "$(dirname "$0")/../sql/indexes.sql"
        log_success "Indexes applied"
    else
        log_warn "No indexes.sql file found"
    fi
}

apply_constraints() {
    log_stage "6. APPLYING CONSTRAINTS"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would apply constraints"
        return 0
    fi
    
    if [[ -f "$(dirname "$0")/../sql/constraints.sql" ]]; then
        log_info "Applying constraints..."
        psql -d "$TARGET_DSN" -f "$(dirname "$0")/../sql/constraints.sql"
        log_success "Constraints applied"
    else
        log_warn "No constraints.sql file found"
    fi
}