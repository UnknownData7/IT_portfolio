#!/bin/bash

PROGRESS_TOTAL=0
PROGRESS_CURRENT=0
PROGRESS_WIDTH=50
declare -A TABLE_PROGRESS

init_progress() {
    PROGRESS_TOTAL=$1
    PROGRESS_CURRENT=0
}

update_progress() {
    local current=$1
    local total=$2
    local table="${3:-}"
    
    PROGRESS_CURRENT=$current
    
    if [[ -n "$table" ]]; then
        TABLE_PROGRESS["$table"]="$current/$total"
    fi
    
    local percentage=$((current * 100 / total))
    local filled=$((current * PROGRESS_WIDTH / total))
    local empty=$((PROGRESS_WIDTH - filled))
    
    local bar="["
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    bar+="]"
    
    printf "\r${BLUE}Progress:${NC} %-${PROGRESS_WIDTH}s %3d%% (%d/%d)" "$bar" "$percentage" "$current" "$total"
    
    if [[ $current -eq $total ]]; then
        echo ""  # New line after completion
    fi
}

show_table_progress() {
    log_info "=== TABLE PROGRESS ==="
    for table in "${!TABLE_PROGRESS[@]}"; do
        echo "  $table: ${TABLE_PROGRESS[$table]}"
    done
    echo "======================"
}

spinner() {
    local pid=$1
    local message="$2"
    local delay=0.1
    local spinstr='|/-\'
    
    printf "${BLUE}${message}...${NC} "
    while kill -0 "$pid" 2>/dev/null; do
        local temp=${spinstr#?}
        printf "\b%c" "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
    done
    printf "\b${GREEN}✓${NC}\n"
}