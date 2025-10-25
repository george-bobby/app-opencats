# Chatwoot - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- OpenAI API key (optional, for data generation)

## Setup Process

### 1. Start the container
```bash
python cli.py chatwoot up
```
Options:
- `-d, --detach` - Run in detached mode

**Important:** The system will automatically prepare the database during startup. This process may take a few minutes on first run.

### 2. Verify the installation
Before proceeding to seed the database, make sure you can visit `http://localhost:3000` without any error. This confirms that the Docker containers are properly running and Chatwoot is accessible.

### 3. Seed the database
```bash
python cli.py chatwoot seed
```

**Note:** Only run the seed command after confirming that `http://localhost:3000` is accessible without errors.

### 4. Access Chatwoot
1. Open `http://localhost:3000/` in your browser
2. Login with the configured credentials:
   - Email: `admin@acme.inc`
   - Password: `Admin@123`

### 5. Generate additional data (optional)
```bash
python cli.py chatwoot generate
```

## Available Commands

### Start Services
```bash
python cli.py chatwoot up [-d]
```
- `up` - Start Chatwoot services
- `-d, --detach` - Run in detached mode

### Stop Services
```bash
python cli.py chatwoot down [-v] [-f]
```
- `down` - Stop services and cleanup
- `-v, --volumes` - Remove volumes as well (deletes all data)
- `-f, --force` - Force remove everything including orphaned containers and prune volumes

### Seed Data
```bash
python cli.py chatwoot seed
```
- Creates initial data including:
  - Onboarding setup
  - Agents
  - Teams
  - Inboxes
  - Labels
  - Custom attributes
  - Canned responses
  - Contacts
  - Campaigns
  - Macros
  - Conversations
  - Message status fixes
  - Conversation timestamp fixes

### Generate Test Data
```bash
python cli.py chatwoot generate [OPTIONS]
```
Options:
- `--agents` - Number of agents to generate (default: 50)
- `--teams` - Number of teams to generate (default: 8)
- `--inboxes` - Number of inboxes to generate (default: 16)
- `--labels` - Number of labels to generate (default: 35)
- `--custom-attributes` - Number of custom attributes to generate (default: 10)
- `--canned-responses` - Number of canned responses to generate (default: 30)
- `--contacts` - Number of contacts to generate (default: 2000)
- `--campaigns` - Number of campaigns to generate (default: 15)
- `--macros` - Number of macros to generate (default: 15)
- `--conversations` - Number of conversations to generate (default: 1000)

## Example Usage

### Basic setup
```bash
python cli.py chatwoot up
# Wait for database preparation to complete
# Verify http://localhost:3000 is accessible
python cli.py chatwoot seed
```

### Generate custom data
```bash
python cli.py chatwoot generate --agents 100 --contacts 5000 --conversations 2000
```

### Clean shutdown
```bash
python cli.py chatwoot down --volumes --force
```

## Configuration

The app uses environment variables for configuration. Default settings include:
- **Database**: PostgreSQL on port 5432
- **Redis**: Redis on port 6379
- **Chatwoot URL**: http://localhost:3000
- **Admin Email**: admin@acme.inc
- **Company**: Acme Inc. (SaaS company)

You can customize these settings by modifying the environment variables or the `config/settings.py` file.
