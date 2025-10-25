# Seed - Deeptune Repository for Backfilling Apps

## Overview

Seed is Deeptune's internal repository for creating realistic test data and backfilling applications. This repository provides a standardized framework for generating production-like datasets across various applications to support development, testing, and demonstration purposes.

## Quick Start

### Prerequisites

- macOS, Linux, or Windows with WSL2
- Git
- Bash/Zsh shell

### Setup

```bash
chmod +x ./setup.sh
./setup.sh
```

This script will:

- Install `uv` (Python package manager)
- Install Python 3.12
- Install all dependencies from `pyproject.toml`
- Set up the virtual environment

### IDE Setup

When you open the repository, you'll be prompted to install recommended VS Code extensions. **Please install them** for:

- Consistent code formatting
- Linting and error detection
- Format on save functionality
- Better development experience

## Development Workflow

### Environment Activation

Always activate the virtual environment before working:

```bash
source .venv/bin/activate
```

### Code Quality

This project uses several tools to maintain code quality:

- **Ruff**: Fast Python linter and formatter (configured in `ruff.toml`)
- **Type hints**: Use type annotations for better code clarity
- **Docstrings**: Document functions and classes using Google-style docstrings

### Running Code Quality Checks

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Fix auto-fixable issues
ruff check . --fix
```

## Architecture & Folder Structure

```
seed/
├── src/
│   ├── cli.py                 # Master CLI entry point
│   ├── common/                # Shared utilities across apps
│   │   └── logger.py         # Centralized logging
│   └── apps/                 # Individual applications
│       ├── app1/
│       ├── app2/
│       └── odoohr/           # Example app structure
├── pyproject.toml            # Python dependencies and project config
├── ruff.toml                 # Code formatting and linting rules
└── setup.sh                 # Environment setup script
```

### App Structure Standard

Every app MUST follow this standardized structure:

```
apps/<app_name>/
├── config/
│   ├── __init__.py
│   └── settings.py           # App configuration and environment variables
|   └── .env                  # Only security sensitive keys(for ex OpenAI keys)
|
├── core/                     # Business logic and data models
│   ├── *.py                 # Core domain models
├── data/                     # Generated or static data files
│   ├── *.json
├── docker/                   # Container configuration
│   ├── Dockerfile
│   ├── compose.yml
│   └── entrypoint.sh
├── enums/                    # Enumeration definitions
│   ├── __init__.py
│   └── *.py
├── helpers/                  # App-specific helper functions
│   ├── __init__.py
│   └── *.py
├── utils/                    # Utility functions and support tools
│   ├── __init__.py
│   └── *.py
├── <app_name>_cli.py        # App-specific CLI commands
├── pyproject.toml           # App-specific dependencies (if needed)
└── README.md                # App-specific documentation for replication
```

## CLI Convention

### Master CLI (`src/cli.py`)

Links all applications through a unified interface:

```bash
cd src
python cli.py <app_name> <command>
```

### App-Specific CLI (`<app_name>_cli.py`)

Each app MUST implement these standard commands:

#### Required Commands

- **`up`**: Start the application environment (Docker containers, services)
- **`seed`**: Execute the data seeding/backfilling process

#### Optional Commands

- **Add them on app to app basis**

### Example Usage

```bash
cd src
python cli.py odoohr up      # Start Odoo HR Docker environment
python cli.py odoohr seed    # Run seeding process
python cli.py odoohr generate #(This one is missing try for frappecrm)
python cli.py odoohr down    # Stop the container
```

## Contributing Guidelines

### Before You Start

1. **Read the app-specific README** in `apps/<app_name>/README.md`
2. **Understand the data model** by reviewing the `core/` directory
3. **Check existing data samples** in the `data/` directory

### Development Process

1. **Create a new branch** from `main` for your work
2. **Activate the virtual environment**: `source .venv/bin/activate`
3. **Make your changes** following the coding standards
4. **Test your changes** thoroughly:
   - Run the `up` command to ensure environment starts correctly
   - Run the `seed` command to verify data generation works
5. **Run code quality checks**: `ruff format . && ruff check .`
6. **Update documentation** if you've changed functionality
7. **Commit with clear, descriptive messages**

### Code Standards

#### General Principles

- **Clarity over cleverness**: Write readable, maintainable code
- **Consistency**: Follow existing patterns and conventions
- **Type safety**: Use type hints wherever possible
- **Error handling**: Handle edge cases and provide meaningful error messages

#### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

#### Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include examples for complex functions
- Update README files when adding new features

### Apps

- [OdooHR Replication README](src/apps/odoohr/README.md)
