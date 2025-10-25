# Odoo Inventory - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`

## Available Commands

### Container Management
- `python cli.py odooinventory up` : Builds and Runs the container, see the cli file for more options.

### Data Seeding
- `python cli.py odooinventory seed` - Create database and seed with sample data

## Setup Process

### Quick Start
```bash
# 1. Start the containers
source .venv/bin/activate && cd src
python cli.py odooinventory up -d #-d for running detached mode.

# 2. Wait for containers to be ready, then seed data
python cli.py odooinventory seed
```

## Access Information
- **URL**: http://localhost:8069
- **Username**: admin
- **Password**: admin
- **Database**: odoo

## Cleanup
```bash
# Stop containers and deleted volumes and data
python cli.py odooinventory down
```


