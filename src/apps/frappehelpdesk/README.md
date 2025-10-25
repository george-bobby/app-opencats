# Frappe Helpdesk - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`

## Setup Process

### 1. Start the container
```bash
python cli.py frappehelpdesk up
```
Options:
- `-d, --detach` - Run in detached mode

**Important:** The initial build process for Frappe Helpdesk may take several minutes to complete. Please be patient during the first-time setup.

### 2. Verify the installation
Before proceeding to seed the database, make sure you can visit `http://helpdesk.localhost` without any error. This confirms that the Docker containers are properly running and the application is accessible.

### 3. Seed the database
```bash
python cli.py frappehelpdesk seed
```

**Note:** Only run the seed command after confirming that `http://helpdesk.localhost` is accessible without errors.

### 4. Access Frappe Helpdesk
1. Open `http://helpdesk.localhost/` in your browser
2. Login with the default credentials:
   - Username: `Administrator`
   - Password: `admin`

## Available Commands

### Start Services
```bash
python cli.py frappehelpdesk up [-d] [--build]
```
- `up` - Start Frappe Helpdesk services
- `-d, --detach` - Run in detached mode
- `--build` - Build the docker image

### Stop Services
```bash
python cli.py frappehelpdesk down [-v] [-f]
```
- `down` - Stop services and cleanup
- `-v, --volumes` - Remove volumes as well (deletes all data)
- `-f, --force` - Force remove everything including orphaned containers and prune volumes

### Seed Data
```bash
python cli.py frappehelpdesk seed
```
- Creates initial data including:
  - User accounts
  - Support categories
  - Sample tickets
  - Email templates
  - Support settings
  - Default workflows

### Generate Test Data
```bash
python cli.py frappehelpdesk generate [OPTIONS]
```
Options:
- `--agents` - Number of agent users to insert (default: 40)
- `--admins` - Number of admin users to insert (default: 10)
- `--customers` - Number of customers to insert (default: 500)
- `--customer-users` - Number of customer users to insert (default: 100)
- `--teams` - Number of teams to generate (default: 5)
- `--tickets` - Number of tickets to insert (default: 300)
- `--tickets-per-batch` - Number of tickets to generate per batch (default: 100)
- `--kb-categories` - Number of knowledge base categories to generate (default: 10)
- `--kb-articles` - Number of knowledge base articles to generate (default: 100)
- `--canned-responses` - Number of canned responses to generate (default: 50)

Example:
```bash
# Generate data with custom values
python cli.py frappehelpdesk generate --agents 20 --tickets 150 --teams 3
```

## Example Usage

### Basic setup
```bash
python cli.py frappehelpdesk up
# Wait for Docker build to complete (several minutes)
# Verify http://helpdesk.localhost is accessible
python cli.py frappehelpdesk seed
```

### Clean shutdown
```bash
python cli.py frappehelpdesk down --volumes --force
```
