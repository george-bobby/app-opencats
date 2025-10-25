#!/bin/bash

# Script to automate command execution inside the hrms-frappe-1 container
# Usage: ./reset.sh [command]
# If no command is provided, it will open an interactive bash shell

set -e

CONTAINER_NAME="crm-frappe-1"

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
  echo "Error: Container $CONTAINER_NAME is not running"
  exit 1
fi

# If arguments are provided, execute them in the container
if [ $# -gt 0 ]; then
  echo "Executing command in $CONTAINER_NAME: $@"
  docker exec "$CONTAINER_NAME" bash -c "$@"
else
  # Default commands to set up HRMS site
  echo "Setting up CRM in $CONTAINER_NAME"
  docker exec "$CONTAINER_NAME" bash -c "
    cd /home/frappe/frappe-bench/sites &&
    bench drop-site crm.localhost \
      --mariadb-root-username root \
      --mariadb-root-password 123 &&
    bench new-site crm.localhost \
      --force \
      --mariadb-root-username root \
      --mariadb-root-password 123 \
      --admin-password admin \
      --no-mariadb-socket &&
    bench --site crm.localhost install-app crm &&
    bench --site crm.localhost set-config developer_mode 1 &&
    bench --site crm.localhost clear-cache &&
    bench --site crm.localhost set-config mute_emails 1 &&
    bench --site crm.localhost set-config throttle_user_limit 1000 --parse &&
    bench --site crm.localhost set-config host_name http://127.0.0.1:8000 &&
    bench use crm.localhost &&
    echo 'CRM reset completed successfully!'
  "
fi