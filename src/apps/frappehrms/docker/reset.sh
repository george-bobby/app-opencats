#!/bin/bash

# Script to automate command execution inside the hrms-frappe-1 container
# Usage: ./reset.sh [command]
# If no command is provided, it will open an interactive bash shell

set -e

CONTAINER_NAME="hrms-frappe-1"

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
  echo "Setting up HRMS in $CONTAINER_NAME"
  docker exec "$CONTAINER_NAME" bash -c "
    cd /home/frappe/frappe-bench/sites &&
    bench drop-site hrms.localhost \
      --mariadb-root-username root \
      --mariadb-root-password 123 &&
    bench new-site hrms.localhost \
      --force \
      --mariadb-root-username root \
      --mariadb-root-password 123 \
      --admin-password admin \
      --no-mariadb-socket &&
    bench --site hrms.localhost install-app hrms &&
    bench --site hrms.localhost set-config developer_mode 1 &&
    bench --site hrms.localhost enable-scheduler &&
    bench --site hrms.localhost clear-cache &&
    bench --site hrms.localhost set-config background_workers 8 --parse &&
    bench --site hrms.localhost set-config throttle_user_limit 1000 --parse &&
    bench --site hrms.localhost set-config host_name http://127.0.0.1:8000 &&
    bench use hrms.localhost &&
    echo 'HRMS reset completed successfully!'
  "
fi