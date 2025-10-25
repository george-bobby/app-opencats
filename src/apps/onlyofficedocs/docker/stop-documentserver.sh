#!/bin/bash

CONTAINER_NAME="onlyofficedocs-container"

if [ "$(sudo docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    sudo docker stop $CONTAINER_NAME
    sudo docker rm $CONTAINER_NAME
    echo "OnlyOffice stopped"
else
    echo "Container not found"
fi

sudo docker volume prune -f
sudo docker system prune -f
