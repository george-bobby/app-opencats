# ownCloud - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`

## Setup Process

### 1. Start the container
```bash
python cli.py owncloud up -d
```


### 2. Unzip the data `hr.zip` in `data/default/hr`

Or specify a custom path:
```bash
python cli.py owncloud seed --path apps/owncloud/data/custom
```

### 3. Available Commands
- `up` - Start ownCloud services with automatic initialization
- `down` - Stop services and cleanup
- `seed` - Upload files and directories to ownCloud via WebDAV APIs

## Access Information
- **URL**: https://localhost:9200
- **Username**: admin
- **Password**: admin
- **WebDAV Endpoint**: https://localhost:9200/remote.php/dav/

## Environment Variables
You can customize the ownCloud connection by setting:
- `OCIS_USER` - ownCloud username (default: admin)
- `OCIS_PASS` - ownCloud password (default: admin)  
- `OCIS_URL` - ownCloud base URL (default: https://localhost:9200)

## File Upload Structure

The seed command uploads files to ownCloud maintaining the local directory structure:

**Local Path**: `apps/owncloud/data/default/hr/documents/sample.txt` (from src/)  
**ownCloud Path**: `files/admin/documents/sample.txt`

## Features

### WebDAV Integration
- Directory creation via MKCOL
- File upload via PUT
- Automatic directory structure preservation
- Error handling and retry logic


### WebDAV Operations
- **MKCOL** - Create directories
- **PUT** - Upload files
- **Basic Auth** - Authentication with admin credentials

## Cleanup
```bash
# Stop containers and delete volumes and data
python cli.py owncloud down
```
