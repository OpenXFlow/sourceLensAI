#!/bin/bash
#
# monitor.sh - Checks the status of critical services.

SERVICES_TO_CHECK=("nginx" "postgresql" "my-app.service")
HAS_ERROR=0

echo "--- Monitoring System Services ---"

for service in "${SERVICES_TO_CHECK[@]}"; do
    # systemctl is-active --quiet "$service"
    # Faking the check for this example
    if (( RANDOM % 5 == 0 )); then # Randomly fail one service
        echo "🔴 STATUS: $service is INACTIVE."
        HAS_ERROR=1
    else
        echo "✅ STATUS: $service is ACTIVE."
    fi
done

if [ $HAS_ERROR -eq 1 ]; then
    echo "Error: One or more services are down!"
    exit 1
else
    echo "All services are running normally."
    exit 0
fi