#!/bin/bash

# Script to automate command execution inside the hrms-frappe-1 container
# Usage: ./reset.sh [command]
# If no command is provided, it will open an interactive bash shell

set -e

CONTAINER_NAME="frappehelpdesk-helpdesk-1"
MYSQL_PASSWORD="123"
ADMIN_PASSWORD="admin"

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
  echo "Setting up helpdesk in $CONTAINER_NAME"
  docker exec "$CONTAINER_NAME" bash -c "
    cd /home/frappe/frappe-bench/sites &&
    bench drop-site helpdesk.localhost \
      --mariadb-root-username root \
      --mariadb-root-password ${MYSQL_PASSWORD} &&
    bench new-site helpdesk.localhost \
      --force \
      --mariadb-root-username root \
      --mariadb-root-password ${MYSQL_PASSWORD} \
      --admin-password ${ADMIN_PASSWORD} \
      --no-mariadb-socket &&
    bench --site helpdesk.localhost install-app helpdesk &&
    bench --site helpdesk.localhost set-config developer_mode 1 &&
    bench --site helpdesk.localhost clear-cache &&
    bench --site helpdesk.localhost set-config mute_emails 1 &&
    bench --site helpdesk.localhost set-config throttle_user_limit 1000 --parse &&
    bench --site helpdesk.localhost set-config host_name http://127.0.0.1:8000 &&
    bench use helpdesk.localhost &&
    echo 'helpdesk reset completed successfully!'
  "
fi