from pathlib import Path

from apps.supabase.utils.postgres import PostgresClient
from common.logger import logger


async def create_tables():
    """
    Execute SQL schema files in the correct order to create database tables.
    Files are executed in alphabetical order based on their numeric prefixes.
    """
    # Get the path to the schemas directory
    current_dir = Path(__file__).parent
    schemas_dir = current_dir.parent / "data" / "schemas"

    if not schemas_dir.exists():
        logger.fail(f"Schemas directory not found: {schemas_dir}")
        raise FileNotFoundError(f"Schemas directory not found: {schemas_dir}")

    # Get all SQL files and sort them (numeric prefixes ensure correct order)
    # The 00_enums.sql file MUST be executed first
    sql_files = sorted([f for f in schemas_dir.iterdir() if f.suffix == ".sql"])

    # Verify that 00_enums.sql exists and is first
    if sql_files and sql_files[0].name != "00_enums.sql":
        logger.fail("Error: 00_enums.sql must be the first file (with prefix 00_)")
        raise ValueError("Schema files must start with 00_enums.sql")

    if not sql_files:
        logger.info("No SQL files found in schemas directory")
        return

    # Use info instead of start to avoid nested status with PostgresClient
    logger.info(f"Found {len(sql_files)} SQL schema files to execute: {', '.join(f.name for f in sql_files)}")

    async with PostgresClient() as postgres:
        for sql_file in sql_files:
            file_path = schemas_dir / sql_file

            try:
                logger.start(f"Executing {sql_file}...")

                # Read the SQL file content
                with Path.open(file_path, encoding="utf-8") as f:
                    sql_content = f.read()

                # Execute the SQL content
                # Split by semicolon to handle multiple statements, but be careful with function definitions
                statements = _split_sql_statements(sql_content)

                for i, statement in enumerate(statements):
                    if statement.strip():  # Skip empty statements
                        try:
                            await postgres.execute(statement)
                        except Exception as e:
                            logger.fail(f"Error executing statement {i + 1} in {sql_file}: {e!s}")
                            logger.info(f"Statement: {statement[:200]}...")
                            # raise

                logger.succeed(f"Successfully executed {sql_file}")

            except Exception as e:
                logger.fail(f"Failed to execute {sql_file}: {e!s}")
                # raise

    logger.succeed("All SQL schema files executed successfully!")


def _split_sql_statements(sql_content: str) -> list[str]:
    """
    Split SQL content into individual statements while handling function definitions properly.
    This is a simplified version that handles most cases.
    """
    statements = []
    current_statement = ""
    in_function = False

    lines = sql_content.split("\n")

    for line in lines:
        stripped_line = line.strip()

        # Skip comments and empty lines
        if not stripped_line or stripped_line.startswith("--"):
            continue

        current_statement += line + "\n"

        # Check if we're entering a function definition
        if "create or replace function" in stripped_line.lower() or "create function" in stripped_line.lower():
            in_function = True

        # Check if we're ending a function definition
        if in_function and stripped_line.lower().startswith("$$ language"):
            in_function = False
            # Look for the semicolon that ends the function
            if ";" in line:
                statements.append(current_statement.strip())
                current_statement = ""
        elif not in_function and stripped_line.endswith(";"):
            # Regular statement ending
            statements.append(current_statement.strip())
            current_statement = ""

    # Add any remaining statement
    if current_statement.strip():
        statements.append(current_statement.strip())

    return statements


async def drop_all_tables():
    """
    Drop all tables in the database.
    """
    async with PostgresClient() as postgres:
        await postgres.execute("DROP SCHEMA public CASCADE;")
        await postgres.execute("CREATE SCHEMA public;")
        await postgres.execute("GRANT ALL ON SCHEMA public TO postgres;")
        await postgres.execute("GRANT ALL ON SCHEMA public TO public;")
        await postgres.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;")
