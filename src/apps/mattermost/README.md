# Mattermost - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- OpenAI/Anthropic API key (optional, for AI-powered message generation)

## Setup Process

### 1. Start the container
```bash
python cli.py mattermost up
```

### 2. Seed the database
```bash
rm -rf src/apps/mattermost/data/channel-messages/*.json
python cli.py mattermost seed
```

### 3. Access Mattermost
1. Open `http://localhost:8065` in your browser
2. Login with default admin credentials:
   - **Email**: `admin@vertexon.com`
   - **Password**: `password@123`

### 4. Generate additional test data (optional)
```bash
python cli.py mattermost generate
```

## Available Commands
- `up` - Start Mattermost services (web app, database, and supporting services)
- `down` - Stop services and cleanup containers and volumes
- `seed` - Initialize Mattermost instance and seed with generated data
- `generate` - Generate test data using AI (teams, users, channels, messages)

## Configuration

### Settings (config/settings.py)
Key configuration options:
- **AI Settings**: `ANTHROPIC_API_KEY`, `DEFAULT_MODEL` (claude-3-5-haiku-latest)
- **Mattermost Config**: `MATTERMOST_URL` (localhost:8065), admin credentials
- **Company Profile**: `COMPANY_DOMAIN` (vertexon.com), `DATA_THEME_SUBJECT`
- **Database**: PostgreSQL connection settings (localhost:5432)
- **Docker Images**: Mattermost Enterprise Edition 10.11, PostgreSQL 13-alpine

All settings can be overridden via environment variables or `.env` file.

