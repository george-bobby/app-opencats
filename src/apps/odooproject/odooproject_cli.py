import asyncio
import subprocess
from pathlib import Path

import click

from apps.odooproject.core.activity_plan import insert_activity_plans
from apps.odooproject.core.activity_type import insert_activity_types
from apps.odooproject.core.module import activate_modules
from apps.odooproject.core.project import insert_project_tags, insert_projects, unfold_all_project_stages
from apps.odooproject.core.settings import insert_settings
from apps.odooproject.core.task import insert_tasks
from apps.odooproject.core.task_stage import insert_task_stages
from apps.odooproject.core.user import insert_users
from apps.odooproject.generators.activity_plan import generate_activity_plans
from apps.odooproject.generators.project import generate_projects
from apps.odooproject.generators.task import generate_tasks
from apps.odooproject.generators.user import generate_users
from apps.odooproject.utils.odoo import create_odoo_db


@click.group()
def odooproject_cli():
    pass


@odooproject_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and create database"""

    # Start docker containers
    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir)


@odooproject_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir)

    print("Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])


@odooproject_cli.command()
@click.option("--n-users", type=int, default=50, help="Number of users to generate")
@click.option("--n-plans", type=int, default=7, help="Number of plans to generate")
@click.option("--n-projects", type=int, default=40, help="Number of projects to generate")
@click.option("--n-tasks", type=int, default=20, help="Number of tasks per project to generate")
def generate(n_users: int, n_plans: int, n_projects: int, n_tasks: int):
    async def generate_odooproject():
        await asyncio.gather(
            generate_users(n_users),
            generate_activity_plans(n_plans),
        )
        await generate_projects(n_projects)
        await generate_tasks(n_tasks)

    asyncio.run(generate_odooproject())


@odooproject_cli.command()
def seed():
    async def async_seed_odooproject():
        await activate_modules()
        await insert_settings()
        await insert_users()
        await insert_activity_types()
        await insert_activity_plans()
        await unfold_all_project_stages()
        await insert_project_tags()
        await insert_task_stages()
        await insert_projects()
        await insert_tasks()

    create_odoo_db()
    asyncio.run(async_seed_odooproject())
