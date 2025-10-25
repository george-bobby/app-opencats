#!bin/bash

if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench already exists, skipping init"
    cd frappe-bench
    echo "Starting bench..."
    bench worker & 
    bench start
else
    echo "Creating new bench..."
fi

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

sudo apt update
sudo apt install xvfb libfontconfig libjpeg62-turbo -y
sudo ln -s /usr/lib/x86_64-linux-gnu/libjpeg.so.62 /usr/lib/x86_64-linux-gnu/libjpeg.so.8
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb
sudo dpkg -i wkhtmltox_0.12.6.1-3.bookworm_amd64.deb
sudo cp /usr/local/bin/wkhtmlto* /usr/bin/
sudo chmod a+x /usr/bin/wk*
sudo rm wk*
sudo apt --fix-broken install -y

bench init --skip-redis-config-generation frappe-bench --frappe-branch version-15

cd frappe-bench

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

bench get-app erpnext --branch version-15
bench get-app hrms --branch version-15

bench new-site hrms.localhost \
--force \
--mariadb-root-username root \
--mariadb-root-password 123 \
--admin-password admin \
--no-mariadb-socket

bench --site hrms.localhost install-app hrms
bench --site hrms.localhost set-config developer_mode 1
bench --site hrms.localhost enable-scheduler
bench --site hrms.localhost clear-cache
bench --site hrms.localhost set-config background_workers 8 --parse
bench --site hrms.localhost set-config throttle_user_limit 1000 --parse
bench --site hrms.localhost set-config host_name http://127.0.0.1:8000
bench use hrms.localhost

bench start