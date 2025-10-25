# Teable - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- OpenAI API key (optional, for data generation)

## Setup Process

### 1. Start the container
```bash
python cli.py teable up
```

### 2. Seed the database
```bash
python cli.py teable seed
```

### 3. Access Teable
1. Open `http://localhost:3000` in your browser
2. Login with default credentials:
   - **Email**: `admin@summittech.com`
   - **Password**: `Admin@123`

### 4. Generate additional data (optional)
```bash
python cli.py teable generate
```

## Available Commands
- `up` - Start Teable services
- `down` - Stop services and cleanup
- `seed` - Create workspaces, bases, and tables
- `generate` - Generate test data using AI

## Login Credentials
- **URL**: http://localhost:3000
- **Email**: `admin@summittech.com`
- **Password**: `Admin@123`
