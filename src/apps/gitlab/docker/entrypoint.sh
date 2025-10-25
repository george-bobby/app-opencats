#!/bin/bash
set -e

echo "🚀 GitLab Import Container Starting..."

# Load configuration
source /app/import.conf

# Wait for GitLab to be ready
echo "⏳ Waiting for GitLab to be ready..."
python3 /app/wait_for_gitlab.py

# Check if tokens are provided
if [ -z "$GITLAB_TOKEN" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Error: GITLAB_TOKEN and GITHUB_TOKEN environment variables are required"
    echo "Please set them in your .env file or docker-compose environment"
    exit 1
fi

# Create logs directory
mkdir -p /app/logs

# Check import mode
case "$IMPORT_MODE" in
    "single")
        if [ -z "$REPO_NAME" ]; then
            echo "❌ Error: REPO_NAME is required for single import mode"
            echo "Usage: docker-compose --profile import run gitlab-importer [repo_name]"
            exit 1
        fi
        echo "📦 Importing single repository: $REPO_NAME"
        exec python3 gitlab_github_import_full.py "$REPO_NAME"
        ;;
    "batch")
        echo "📦 Importing all repositories from config..."
        python3 -c "
import sys
sys.path.append('/app')
from config.settings import load_config
config = load_config()
if not config:
    print('❌ No repositories found in config')
    sys.exit(1)
    
for repo_name in config.keys():
    print(f'📦 Importing {repo_name}...')
    import subprocess
    result = subprocess.run([sys.executable, 'gitlab_github_import_full.py', repo_name], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print(f'✅ {repo_name} imported successfully')
    else:
        print(f'❌ {repo_name} import failed: {result.stderr}')
        print(f'Stdout: {result.stdout}')
"
        ;;
    "interactive")
        echo "🔧 Interactive mode - starting shell"
        exec /bin/bash
        ;;
    *)
        echo "📋 Available repositories:"
        python3 -c "
import sys
sys.path.append('/app')
from config.settings import load_config
config = load_config()
if config:
    for repo_name, repo_url in config.items():
        print(f'  • {repo_name}: {repo_url}')
else:
    print('  No repositories configured')
"
        echo ""
        echo "Usage examples:"
        echo "  Single import: docker-compose --profile import run gitlab-importer [repo_name]"
        echo "  Batch import:  IMPORT_MODE=batch docker-compose --profile import up gitlab-importer"
        echo "  Interactive:   IMPORT_MODE=interactive docker-compose --profile import run gitlab-importer"
        exit 0
        ;;
esac 