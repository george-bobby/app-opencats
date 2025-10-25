# Apache Superset - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`

## Setup Process

### 1. Start the container
```bash
python cli.py superset up
```

### 2. Access Apache Superset
1. Wait for initialization to complete (this may take a few minutes on first run)
2. Open `http://localhost:8088` in your browser
3. Login with default credentials:
   - **Username**: `admin`
   - **Password**: `admin`

## Available Commands
- `up` - Start Superset services
  - `--detach` or `-d` - Run in detached mode
- `down` - Stop services and cleanup
  - `--volumes` or `-v` - Remove volumes as well (deletes all data)
  - `--force` or `-f` - Force remove everything including orphaned containers

## Login Credentials
- **URL**: http://localhost:8088
- **Username**: `admin`
- **Password**: `admin`

## Notes
- The first startup may take several minutes as it downloads images and initializes the database
- Example datasets are loaded by default to help you get started
- All data is persisted in Docker volumes - use `down --volumes` to reset completely
