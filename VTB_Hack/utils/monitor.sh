# utils/monitor.sh
monitor_performance() {
    local table="$1"
    local start_time=$(date +%s)
    
    # ... migration code ...
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local rows_per_second=$((total_rows / duration))
    
    log_info "Performance: $table - $rows_per_second rows/second"
}