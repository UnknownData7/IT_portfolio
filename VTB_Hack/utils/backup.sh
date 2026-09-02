# utils/backup.sh
create_backup() {
    local backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    log_info "Creating backup: $backup_file"
    pg_dump -d "$TARGET_DSN" > "$WORK_DIR/backups/$backup_file"
}