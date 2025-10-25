import asyncio
import subprocess
from pathlib import Path

import click

from apps.odoohr.core.accrual_plan import insert_accrual_plans
from apps.odoohr.core.allocation import insert_time_off_allocations
from apps.odoohr.core.candidate import insert_candidates
from apps.odoohr.core.department import insert_departments
from apps.odoohr.core.employee import insert_employee_categories, insert_employees
from apps.odoohr.core.group import insert_groups
from apps.odoohr.core.industry import insert_industry
from apps.odoohr.core.job_position import insert_job_positions
from apps.odoohr.core.module import activate_modules
from apps.odoohr.core.public_holiday import insert_public_holidays
from apps.odoohr.core.skill import insert_skills
from apps.odoohr.core.time_off import insert_time_off
from apps.odoohr.core.time_off_type import insert_time_off_types
from apps.odoohr.core.working_schedule import insert_working_schedules
from apps.odoohr.utils.odoo import create_odoo_db


# from apps.odoohr.generators.candidate import generate_candidates
# from apps.odoohr.generators.job_position import generate_job_positions


@click.group()
def odoohr_cli():
    pass


@odoohr_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and create database"""

    # Start docker containers
    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir)


@odoohr_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir)

    print("Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])


# @odoohr_cli.command()
# @click.option("--n-jobs", type=int, default=40, help="Number of job positions to generate")
# @click.option("--n-candidates", type=int, default=60, help="Number of candidates to generate")
# def generate(n_candidates: int, n_jobs: int):
#     async def generate_odoohr():
#         await generate_job_positions(n_jobs)
#         await generate_candidates(n_candidates)

#     asyncio.run(generate_odoohr())


@odoohr_cli.command()
def seed():
    async def async_seed_odoohr():
        await activate_modules()
        await insert_industry()
        await insert_groups()
        await insert_skills()
        await insert_employee_categories()
        await asyncio.sleep(5)
        await insert_departments()
        await insert_job_positions()
        await insert_employees()
        await insert_public_holidays()
        await insert_working_schedules()
        await insert_accrual_plans()
        await insert_time_off_types()
        await insert_time_off_allocations()
        await insert_time_off()
        await insert_candidates()

    create_odoo_db()
    asyncio.run(async_seed_odoohr())
