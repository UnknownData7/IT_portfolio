#!/bin/bash

run_cmd() {
    local cmd="$1"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: $cmd"
        return 0
    fi
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "EXECUTING: $cmd"
    fi
    
    eval "$cmd"
}

dry_run_summary() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_stage "=== DRY RUN SUMMARY ==="
        log_info "Source: $(echo "$SOURCE_DSN" | sed 's/:[^:]*@/:***@/')"
        log_info "Target: $(echo "$TARGET_DSN" | sed 's/:[^:]*@/:***@/')"
        
        local tables=($(get_tables_to_migrate))
        log_info "Tables to migrate: ${#tables[@]}"
        log_info "Threads: $THREADS"
        
        for table in "${tables[@]:0:10}"; do
            log_info "  - $table"
        done
        if [[ ${#tables[@]} -gt 10 ]]; then
            log_info "  - ... and $(( ${#tables[@]} - 10 )) more"
        fi
        
        log_stage "=== END DRY RUN ==="
    fi
}