# Copilot Instructions for Seed (Deeptune App Backfilling Repository)

## Project Overview

Seed is a standardized framework for generating production-like test data across multiple applications. Each app follows a strict modular architecture pattern with Docker orchestration and AI-driven data generation.

## Architecture Patterns

### App Structure (STRICTLY ENFORCED)

Every app MUST follow this exact structure - use `src/apps/medusa/` as the reference implementation:

```
apps/<app_name>/
├── <app_name>_cli.py     # CLI with mandatory commands: up, down, generate, seed
├── config/
│   ├── settings.py       # Pydantic settings with .env support
│   └── constants.py      # Enums and app constants
├── core/                 # Business logic - seeding functions organized by entity
├── data/                 # Generated JSON data files
├── docker/               # Complete Docker Compose setup
├── utils/                # App-specific utilities
└── README.md            # App replication documentation
```

### CLI Integration Pattern

1. **Master CLI**: All apps register in `src/cli.py` using Click groups
2. **App CLI Commands**: Each app implements exactly these 4 commands:
   - `up`: Start Docker environment (with `-d/--detach` flag)
   - `down`: Stop containers with cleanup (`--remove-orphans --volumes`)
   - `generate`: AI-driven data generation (some apps may not have this yet)
   - `seed`: Execute data backfilling process

### Configuration Pattern

- Use `pydantic_settings.BaseSettings` with `.env` file support
- Store sensitive keys (OpenAI, Anthropic) in config/.env
- Use Path objects for file paths: `Path(__file__).parent.parent.joinpath("data")`
- Follow the settings structure from `apps/medusa/config/settings.py`

## Development Workflow

### Environment Setup

```bash
# Always start with this
./setup.sh                          # Sets up uv, Python 3.12, dependencies
source .venv/bin/activate           # Activate virtual environment
cd src                              # Work from src directory
```

### Common Commands

```bash
# App operations
python cli.py <app_name> up -d      # Start app in detached mode
python cli.py <app_name> seed       # Run data seeding
python cli.py <app_name> down       # Clean shutdown

# Code quality (run before commits)
ruff format .                       # Format code
ruff check . --fix                  # Fix linting issues
```

### Adding New Apps

1. **Copy structure**: Use `apps/medusa/` as template - don't deviate
2. **Update master CLI**: Add import and command registration in `src/cli.py`
3. **Update dependencies**: Add any new packages to root `pyproject.toml`
4. **Follow naming**: Use exact naming conventions (`snake_case` for files, etc.)

## Code Patterns

### Logging

- Use shared logger: `from common.logger import logger`
- Log with emoji indicators: `logger.info("🚀 Starting...")`, `logger.succeed("✅ Complete!")`
- Use status tracking for long operations with elapsed time

### Error Handling

- Handle Docker failures gracefully in CLI commands
- Use async/await for API calls and database operations
- Implement proper connection pooling for databases

### Data Generation

- Set consistent random seed: `random.seed(RANDOM_SEED)` from constants
- Use Anthropic/OpenAI clients from `common/` for AI generation
- Structure generated data as clean JSON in `data/` directory
- Follow realistic data patterns - this is for production-like testing

### Database Integration

- Use async database clients (asyncpg, aiomysql)
- Implement connection management in core modules
- Follow the seeding pattern: delete → generate → seed → verify

## Key Files to Reference

- **`apps/medusa/medusa_cli.py`**: Perfect CLI implementation example
- **`apps/medusa/config/settings.py`**: Configuration pattern
- **`src/cli.py`**: Master CLI registration pattern
- **`common/logger.py`**: Shared logging utilities
- **`ruff.toml`**: Code quality standards (188 char line length, Python 3.12)

## Docker Patterns

- Each app has self-contained `docker/` directory with `compose.yml`
- Use `--build` flag for reliability: `docker compose up --build`
- Include cleanup in down command: `docker compose down --remove-orphans --volumes`
- Follow volume cleanup pattern: `docker volume prune -f`

## Critical Rules

1. **Never deviate from medusa app structure** - it's the ground truth
2. **Always implement all 4 CLI commands** - up, down, generate, seed
3. **Update pyproject.toml** when adding dependencies
4. **Use absolute paths** and proper Path objects
5. **Follow async patterns** for external API calls
6. **Maintain realistic data quality** - this supports actual development/testing

The goal is production-ready data generation with zero surprises - every app should work identically.
