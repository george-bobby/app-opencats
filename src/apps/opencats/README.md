# OpenCATS Seeding Configuration

## Overview

This directory contains the configuration setup for OpenCATS data seeding, designed to be compatible with both Docker and local development environments.

### Structure

```
apps/opencats/
├── config/
│   ├── __init__.py
│   ├── constants.py          # Model names and database constants
├── core/                     # Business logic and data models
│   ├── generate/             # Core generate files
│   │    ├── *.py
│   ├── *.py                  # Core domain models
├── data/                     # Generated or static data files
│   ├── *.json
├── docker/                   # Container configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
├── utils/                    # Utility functions and support tools
│   ├── __init__.py
│   └── *.py
├── opencats_cli.py             # App-specific CLI commands
└── README.md                 # This file
```

### Example Usage

```bash
cd src
python cli.py opencats up      # Start opencats Docker environment
python python cli.py opencats generate --n-companies 100 --n-contacts 300 --n-candidates 500    # Run seeding process
python cli.py opencats seed #(This one is missing try for frappecrm)
python cli.py opencats down    # Stop the container
```

### Notes

- 🕐 Startup Time: The OpenCATS container typically takes around 5 minutes to start up.
- ⏳ Seeding Duration: The seed command may take approximately 25–30 minutes to complete.

### Start the application

1. Open the specified URL `localhost/`
2. Credentials:
   a. **Email**: <admin@example.com>
   b. **Password**: supersecret

## Contributing

When adding new configuration options:

1. Add constants to `constants.py`
2. Add settings to `settings.py`
3. Update this README
