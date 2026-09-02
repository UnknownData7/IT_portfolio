#!/bin/bash

# Конфигурационные переменные
CONFIG_FILE=""
SOURCE_DSN=""
TARGET_DSN=""
TABLES=""
THREADS=4
DRY_RUN="false"
VERBOSE="false"
WORK_DIR="work"

declare -A WHERE_CLAUSES
declare -A COPY_WHERE_CLAUSES

load_config() {
    CONFIG_FILE="$1"
    THREADS="${2:-4}"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Config file $CONFIG_FILE not found"
        exit 1
    fi
    
    source "$CONFIG_FILE"
    
    # Проверка обязательных параметров
    local required_vars=("SOURCE_DSN" "TARGET_DSN")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_error "Missing required configuration: $var"
            exit 1
        fi
    done
    
    log_info "Configuration loaded: $CONFIG_FILE"
}

setup_work_dirs() {
    mkdir -p "$WORK_DIR"/{logs,dumps,temp}
    log_info "Work directories created: $WORK_DIR/"
}

get_config_summary() {
    echo "=== Migration Configuration ==="
    echo "Source: $(echo "$SOURCE_DSN" | sed 's/:[^:]*@/:***@/')"
    echo "Target: $(echo "$TARGET_DSN" | sed 's/:[^:]*@/:***@/')"
    echo "Tables: ${TABLES:0:50}..."
    echo "Threads: $THREADS"
    echo "Dry Run: $DRY_RUN"
    echo "==============================="
}