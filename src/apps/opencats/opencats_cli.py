"""OpenCATS CLI module for data generation and seeding operations."""

import asyncio
import subprocess
from pathlib import Path

import click

from apps.opencats.config.constants import (
    DEFAULT_CANDIDATES_COUNT,
    DEFAULT_COMPANIES_COUNT,
    DEFAULT_CONTACTS_COUNT,
    DEFAULT_EVENTS_COUNT,
    DEFAULT_JOBORDERS_COUNT,
    DEFAULT_LISTS_COUNT,
)
from apps.opencats.core.candidates import seed_candidates
from apps.opencats.core.companies import seed_companies, update_companies_billing_contacts
from apps.opencats.core.contacts import seed_contacts
from apps.opencats.core.database import clear_seeded_data
from apps.opencats.core.events import seed_events
from apps.opencats.core.joborders import create_candidate_job_associations, seed_joborders
from apps.opencats.core.lists import seed_lists
from apps.opencats.generate.generate_candidates import candidates
from apps.opencats.generate.generate_companies import companies
from apps.opencats.generate.generate_contacts import contacts
from apps.opencats.generate.generate_events import events
from apps.opencats.generate.generate_joborders import joborders
from apps.opencats.generate.generate_lists import lists
from common.logger import logger


@click.group()
def opencats_cli():
    """OpenCATS Seeding CLI - Manage OpenCATS data seeding and Docker operations"""
    pass


@opencats_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and start OpenCATS services"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    logger.info("🚀 Starting OpenCATS Docker containers...")
    subprocess.run(cmd, cwd=docker_dir)
    logger.succeed("✅ OpenCATS containers started successfully!")


@opencats_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    logger.info("🛑 Stopping OpenCATS Docker containers...")
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir)

    logger.info("🧹 Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])
    logger.succeed("✅ Cleanup completed!")


@opencats_cli.command()
def clear():
    """Clear only the seeded data, preserving users and system tables"""

    async def async_clear_data():
        """Async function to clear seeded data"""
        logger.info("🧹 Starting seeded data cleanup...")
        await clear_seeded_data()

    asyncio.run(async_clear_data())


@opencats_cli.command()
def seed():
    """Seed OpenCATS with generated data"""

    async def async_seed_opencats():
        """Async function to seed OpenCATS data"""
        logger.info("🌱 Starting OpenCATS data seeding...")

        # Seed data in dependency order
        await seed_companies()
        await seed_contacts()
        
        # Update companies with billing contact assignments
        await update_companies_billing_contacts()
        
        await seed_candidates()
        await seed_joborders()
        
        # Create candidate-job associations
        await create_candidate_job_associations()
        
        await seed_events()
        await seed_lists()

        logger.succeed("✅ OpenCATS data seeding completed!")

    asyncio.run(async_seed_opencats())


@opencats_cli.command()
@click.option("--n-companies", type=int, default=DEFAULT_COMPANIES_COUNT, help="Number of companies to generate")
@click.option("--n-contacts", type=int, default=DEFAULT_CONTACTS_COUNT, help="Number of contacts to generate")
@click.option("--n-candidates", type=int, default=DEFAULT_CANDIDATES_COUNT, help="Number of candidates to generate")
@click.option("--n-joborders", type=int, default=DEFAULT_JOBORDERS_COUNT, help="Number of job orders to generate")
@click.option("--n-events", type=int, default=DEFAULT_EVENTS_COUNT, help="Number of calendar events to generate")
@click.option("--n-lists", type=int, default=DEFAULT_LISTS_COUNT, help="Number of saved lists to generate")
def generate(
    n_companies: int,
    n_contacts: int,
    n_candidates: int,
    n_joborders: int,
    n_events: int,
    n_lists: int,
):
    """Generate OpenCATS data using AI"""

    async def async_generate():
        logger.info("🎲 Starting OpenCATS data generation...")
        logger.info(f"📊 Target counts: companies={n_companies}")
        logger.info(f"📊 Target counts: candidates={n_candidates}")
        logger.info(f"📊 Target counts: contacts={n_contacts}")
        logger.info(f"📊 Target counts: joborders={n_joborders}")
        logger.info(f"📊 Target counts: events={n_events}")
        logger.info(f"📊 Target counts: lists={n_lists}")

        # Generate data in dependency order for proper mapping
        await companies(n_companies)
        await contacts(n_contacts)
        await candidates(n_candidates)
        await joborders(n_joborders)
        await events(n_events)
        await lists(n_lists)

        logger.succeed("✅ OpenCATS data generation completed!")

    asyncio.run(async_generate())


if __name__ == "__main__":
    opencats_cli()
