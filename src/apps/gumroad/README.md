# Gumroad - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- OpenAI API key (optional, for data generation)

## Setup Process

### 1. Start the container
```bash
python cli.py gumroad up
```
Options:
- `-d, --detach` - Run in detached mode
- `--build` - Build the docker image

**Important:** You have to wait quite long for the build inside Docker for Gumroad to complete before using the tool. This initial build process can take several minutes.

### 2. Verify the installation
Before proceeding to seed the database, make sure you can visit `http://gumroad.localhost` without any error. This confirms that the Docker containers are properly running and the application is accessible.

### 3. Seed the database
```bash
python cli.py gumroad seed
```

**Note:** Only run the seed command after confirming that `http://gumroad.localhost` is accessible without errors.

### 4. Access Gumroad
1. Open `http://gumroad.localhost/` in your browser
2. Login with the configured credentials

### 5. Generate additional data (optional)
```bash
python cli.py gumroad generate
```

## Available Commands

### Start Services
```bash
python cli.py gumroad up [-d] [--build]
```
- `up` - Start Gumroad services
- `-d, --detach` - Run in detached mode
- `--build` - Build the docker image

### Stop Services
```bash
python cli.py gumroad down [-v] [-f]
```
- `down` - Stop services and cleanup
- `-v, --volumes` - Remove volumes as well (deletes all data)
- `-f, --force` - Force remove everything including orphaned containers and prune volumes

### Seed Data
```bash
python cli.py gumroad seed
```
- Creates initial data including:
  - Profile setup
  - Products
  - Discounts
  - Checkout forms
  - Workflows
  - Emails
  - Sales
  - Product views
  - Payouts
  - Analytics indices

### Generate Test Data
```bash
python cli.py gumroad generate [OPTIONS]
```
Options:
- `-p, --products` - Number of products to generate (default: 15)
- `-d, --discounts` - Number of discounts to generate (default: 20)
- `-w, --workflows` - Number of workflows to generate (default: 5)
- `-e, --emails` - Number of emails to generate (default: 10)
- `-s, --sales` - Number of sales to generate (default: 500)
- `-f, --followers` - Number of followers to generate (default: 2000)
- `-v, --views` - Number of product views to generate (default: 20000)
- `-p, --payouts` - Number of payouts to generate (default: 24)

## Example Usage

### Basic setup
```bash
python cli.py gumroad up
# Wait for Docker build to complete (several minutes)
# Verify http://gumroad.localhost is accessible
python cli.py gumroad seed
```

### Generate custom data
```bash
python cli.py gumroad generate --products 50 --sales 1000 --followers 5000
```

### Clean shutdown
```bash
python cli.py gumroad down --volumes --force
```
