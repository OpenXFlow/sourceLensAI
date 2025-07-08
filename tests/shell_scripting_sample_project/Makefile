# Makefile for orchestrating server tasks on Linux

# Variables
APP_DIR := /var/www/my_app
BACKUP_DIR := /var/backups
GIT_REPO := https://github.com/example/my-app.git

.PHONY: all backup deploy monitor clean

all: deploy

# Create a backup of the application and database
backup:
    @echo "Starting backup process..."
    @bash linux/backup.sh $(BACKUP_DIR) $(APP_DIR)
    @echo "Backup completed."

# Deploy the latest version of the application
deploy:
    @echo "Starting deployment..."
    @bash linux/deploy.sh $(APP_DIR) $(GIT_REPO)
    @echo "Deployment finished."

# Monitor the status of required services
monitor:
    @echo "Monitoring services..."
    @bash linux/monitor.sh

clean:
    @echo "Cleaning up temporary files..."
    @rm -f /tmp/app_*.log