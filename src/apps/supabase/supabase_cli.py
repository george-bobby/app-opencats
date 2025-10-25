import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.supabase.config.settings import settings
from apps.supabase.core.authentication import generate_authentication_data, seed_authentication_users
from apps.supabase.core.brands import generate_brand_data, seed_brands_data
from apps.supabase.core.images import generate_images_data, generate_uploaded_images_metadata, seed_images_data
from apps.supabase.core.meal_logs import generate_meal_logs_data, seed_meal_logs_data
from apps.supabase.core.meals import generate_meals_data, seed_meals_data
from apps.supabase.core.storage import create_storage_buckets, upload_storage_content
from apps.supabase.core.tables import create_tables
from apps.supabase.core.users import generate_user_preferences_data, generate_users_data, seed_user_preferences_data, seed_users_data


@click.group()
def supabase_cli():
    pass


@supabase_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}
    cmd = ["docker", "compose", "-v", "up"]

    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir, env=env)


@supabase_cli.command()
@click.option("-v", "--volumes", is_flag=True, help="Remove volumes as well (deletes all data)")
@click.option("-f", "--force", is_flag=True, help="Force remove everything including orphaned containers and prune volumes")
def down(volumes: bool, force: bool):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    if volumes:
        cmd.append("--volumes")

    subprocess.run(cmd, cwd=docker_dir, env=env)

    # If force is specified, also prune volumes to ensure complete cleanup
    if force:
        print("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"])


@supabase_cli.command()
def seed():
    """Seed the supabase database with test data"""

    async def async_seed_supabase():
        await create_tables()
        await create_storage_buckets()

        await seed_authentication_users()
        await seed_users_data()
        await seed_user_preferences_data()
        await seed_brands_data()
        await seed_meals_data()
        await upload_storage_content()
        await seed_images_data()
        await seed_meal_logs_data()

    asyncio.run(async_seed_supabase())


@supabase_cli.command()
@click.option("--users", default=300, help="Number of users to generate")
@click.option("--brands", default=300, help="Number of brands to generate")
@click.option("--meals", default=3000, help="Number of meals to generate")
@click.option("--logs", default=9000, help="Number of meal logs to generate")
def generate(users: int, brands: int, meals: int, logs: int):
    """Generate user data and save to JSON files"""

    async def async_generate_data():
        # First generate users and authentication
        await generate_authentication_data(users)
        await generate_users_data()
        await generate_user_preferences_data()

        # Then generate brands and meals (meals depend on brands)
        await generate_brand_data(brands)
        await generate_meals_data(meals)

        # Next generate images (depends on users)
        await generate_uploaded_images_metadata()
        await generate_images_data()

        # Finally generate meal logs (depends on users, meals, and optionally images)
        await generate_meal_logs_data(logs)

    asyncio.run(async_generate_data())
