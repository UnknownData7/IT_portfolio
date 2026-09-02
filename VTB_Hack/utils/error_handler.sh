#!/bin/bash

set -euo pipefail

declare -a ERROR_LOG
ERROR_COUNT=0
WARNING_COUNT=0

# Основная функция обработки ошибок
handle_error() {
    local exit_code=$?
    local command="$BASH_COMMAND"
    local line_no="$1"
    
    if [[ $exit_code -ne 0 ]]; then
        ERROR_COUNT=$((ERROR_COUNT + 1))
        local error_msg="Error in $0 at line $line_no: '$command' (exit code: $exit_code)"
        
        ERROR_LOG+=("$error_msg")
        log_error "$error_msg"
    fi
    
    return 0
}

# Ловушка для ошибок
trap 'handle_error $LINENO' ERR

# Функция для безопасного выполнения команд с повторами
run_with_retry() {
    local cmd="$1"
    local max_attempts="${2:-3}"
    local delay="${3:-5}"
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if eval "$cmd"; then
            return 0
        fi
        
        log_warn "Attempt $attempt failed for: ${cmd:0:100}..."
        
        if [[ $attempt -eq $max_attempts ]]; then
            log_error "All $max_attempts attempts failed for command"
            return 1
        fi
        
        sleep $delay
        attempt=$((attempt + 1))
    done
}

# Проверка зависимостей
check_dependencies() {
    local deps=("psql" "pg_dump" "pg_dumpall")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Please install: sudo apt-get install postgresql-client"
        exit 1
    fi
}

# Валидация подключения к БД
validate_database_connection() {
    local dsn="$1"
    local db_type="$2"
    
    log_info "Validating $db_type database connection..."
    
    if ! run_with_retry "psql \"$dsn\" -c 'SELECT 1;' >/dev/null 2>&1" 3 2; then
        log_error "Cannot connect to $db_type database: $dsn"
        return 1
    fi
    
    return 0
}

# Финальный отчет об ошибках
error_summary() {
    if [[ $ERROR_COUNT -gt 0 || $WARNING_COUNT -gt 0 ]]; then
        log_stage "=== EXECUTION SUMMARY ==="
        
        if [[ $ERROR_COUNT -gt 0 ]]; then
            log_error "Errors: $ERROR_COUNT"
            for error in "${ERROR_LOG[@]}"; do
                echo "  - $error"
            done
        fi
        
        if [[ $WARNING_COUNT -gt 0 ]]; then
            log_warn "Warnings: $WARNING_COUNT"
        fi
        
        if [[ $ERROR_COUNT -eq 0 ]]; then
            log_success "Migration completed with warnings"
            return 0
        else
            log_error "Migration completed with errors"
            return 1
        fi
    fi
    
    return 0
}

# Логирование предупреждений
log_warning() {
    WARNING_COUNT=$((WARNING_COUNT + 1))
    log_warn "$1"
}