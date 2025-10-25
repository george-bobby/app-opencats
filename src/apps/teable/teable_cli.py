import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.teable.config.settings import settings
from apps.teable.core.attachments import insert_attachments
from apps.teable.core.bases import insert_bases
from apps.teable.core.tables import generate_tables, insert_tables
from apps.teable.core.workspaces import (
    delete_all_workspace,
    generate_workspace_assignments,
    insert_workspace_assignments,
    insert_workspaces,
)
from apps.teable.utils.teable import close_global_client


@click.group()
def teable_cli():
    pass


@teable_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""
    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir, env=env)


@teable_cli.command()
@click.option("-v", "--volumes", is_flag=True, help="Remove volumes as well (deletes all data)")
@click.option("-f", "--force", is_flag=True, help="Force remove everything including orphaned containers and prune volumes")
def down(volumes: bool, force: bool):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    env = {**os.environ, **settings.model_dump_str()}
    if volumes:
        cmd.append("--volumes")

    subprocess.run(cmd, cwd=docker_dir, env=env)

    # If force is specified, also prune volumes to ensure complete cleanup
    if force:
        print("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"])


@teable_cli.command()
def seed():
    async def async_seed_teable():
        try:
            await delete_all_workspace()
            await insert_workspaces()
            await insert_workspace_assignments()
            await insert_bases()
            await insert_tables()
            await insert_attachments()
        finally:
            await close_global_client()

    asyncio.run(async_seed_teable())


@teable_cli.command()
@click.option("-n", "--number-of-users-per-workspace", type=int, default=35, help="Number of users per workspace")
def generate(number_of_users_per_workspace: int):
    async def async_generate_teable():
        try:
            await generate_workspace_assignments(number_of_users_per_workspace)
            await generate_tables()
        finally:
            # Always close the global client, even if there's an exception
            await close_global_client()

    asyncio.run(async_generate_teable())
