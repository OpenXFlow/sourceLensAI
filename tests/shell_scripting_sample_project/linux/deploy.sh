#!/bin/bash
#
# deploy.sh - Deploys the application from a Git repository.

set -e

APP_DIR=$1
GIT_REPO=$2

if [ -z "$APP_DIR" ]; then
    echo "Error: Application directory not specified."
    exit 1
fi

echo "--- Deploying to $APP_DIR ---"

if [ -d "$APP_DIR/.git" ]; then
    echo "Git repository found. Pulling latest changes..."
    cd "$APP_DIR"
    git pull origin main
else
    echo "Cloning new repository from $GIT_REPO..."
    git clone "$GIT_REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

echo "--- Installing dependencies ---"
# Example for a Node.js app
# npm install --production

# Example for a Python app
# pip install -r requirements.txt
echo "Simulating dependency installation."

echo "--- Restarting application service ---"
# sudo systemctl restart my-app.service
echo "Simulating service restart."

echo "Deployment successful."
exit 0