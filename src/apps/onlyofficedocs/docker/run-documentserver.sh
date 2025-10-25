#!/bin/bash

CONTAINER_NAME="onlyofficedocs-container"
IMAGE_NAME="onlyoffice/documentserver"
JWT_SECRET="my_jwt_secret"

# Remove existing container
if [ "$(sudo docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    sudo docker stop $CONTAINER_NAME >/dev/null 2>&1
    sudo docker rm $CONTAINER_NAME >/dev/null 2>&1
fi

# Start container
sudo docker run -i -t -d -p 80:80 --restart=always --name $CONTAINER_NAME -e JWT_SECRET=$JWT_SECRET $IMAGE_NAME

# Wait and configure
sleep 10
sudo docker exec $CONTAINER_NAME sudo supervisorctl start ds:example
sudo docker exec $CONTAINER_NAME sudo sed 's,autostart=false,autostart=true,' -i /etc/supervisor/conf.d/ds-example.conf

echo "OnlyOffice running at http://localhost/example/"
