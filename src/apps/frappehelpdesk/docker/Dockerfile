FROM frappe/bench:latest

# Set up Node.js path
ENV NVM_DIR=/home/.nvm
ENV PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

WORKDIR /home/frappe

RUN bench init --skip-redis-config-generation frappe-bench --version version-15

WORKDIR /home/frappe/frappe-bench

RUN bench get-app helpdesk --branch v1.12.1
RUN bench build --app helpdesk --force

COPY init.sh /home/frappe/frappe-bench/init.sh

CMD ["bash", "init.sh"]
