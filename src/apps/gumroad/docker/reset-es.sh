#!/bin/bash

# Container name variable
CONTAINER_NAME="gumroad-web-1"

echo "Connecting to $CONTAINER_NAME container and running DevTools.delete_all_indices_and_reindex_all..."
echo "This will delete all Elasticsearch indices and reindex everything."
echo ""

# Execute the Rails command in the container
docker exec -i $CONTAINER_NAME bin/rails c << 'EOF'
DevTools.delete_all_indices_and_reindex_all
exit
EOF

echo ""
echo "DevTools reindexing completed."
