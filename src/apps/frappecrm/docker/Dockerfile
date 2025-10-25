FROM frappe/bench:v5.25.9

# Set up Node.js path
ENV NVM_DIR=/home/.nvm
ENV PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

WORKDIR /home/frappe

RUN bench init --skip-redis-config-generation frappe-bench

WORKDIR /home/frappe/frappe-bench

RUN bench get-app crm --branch pot_develop_2025-07-06

COPY init.sh /home/frappe/frappe-bench/init.sh

CMD ["bash", "init.sh"]
