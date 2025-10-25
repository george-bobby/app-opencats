#!/bin/bash

SITE=crm.localhost

cd /home/frappe/frappe-bench

if [ -d "/home/frappe/frappe-bench/sites/$SITE" ]; then
    echo "Bench already exists, skipping init"
    echo "Starting bench..."
    bench worker & 
    bench start
else
    echo "Creating new bench..."
fi

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

bench new-site $SITE \
--force \
--mariadb-root-username root \
--mariadb-root-password 123 \
--admin-password admin \
--no-mariadb-socket

bench --site $SITE install-app crm
bench --site $SITE set-config developer_mode 1
bench --site $SITE clear-cache
bench --site $SITE set-config mute_emails 1
bench --site $SITE set-config throttle_user_limit 1000 --parse
bench --site $SITE set-config host_name http://127.0.0.1:8000
bench use $SITE

bench start