#!/bin/bash
#
# backup.sh - Creates a backup of specified directories and a database.

set -e

BACKUP_DEST=$1
APP_SOURCE=$2
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DEST/app_backup_$TIMESTAMP.tar.gz"
DB_DUMP_FILE="/tmp/db_dump_$TIMESTAMP.sql"

if [ -z "$BACKUP_DEST" ] || [ -z "$APP_SOURCE" ]; then
    echo "Usage: $0 <backup_destination_dir> <app_source_dir>"
    exit 1
fi

echo "--- Backing up database ---"
# mysqldump -u user -p'password' my_database > $DB_DUMP_FILE
echo "Simulating database dump to $DB_DUMP_FILE"
touch $DB_DUMP_FILE

echo "--- Creating archive ---"
tar -czf "$BACKUP_FILE" -C "$(dirname "$APP_SOURCE")" "$(basename "$APP_SOURCE")" -C "/tmp" "$(basename "$DB_DUMP_FILE")"

echo "--- Cleaning up temporary files ---"
rm -f $DB_DUMP_FILE

echo "Backup created successfully at $BACKUP_FILE"
exit 0