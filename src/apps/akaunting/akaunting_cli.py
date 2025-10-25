import asyncio
import subprocess
from pathlib import Path

import click

from apps.akaunting.core.accounts import import_payment_accounts
from apps.akaunting.core.bills import create_generated_bills
from apps.akaunting.core.categories import create_generated_categories
from apps.akaunting.core.contacts import create_customers, create_vendors
from apps.akaunting.core.currencies import import_currencies
from apps.akaunting.core.invoices import create_generated_invoices
from apps.akaunting.core.items import create_generated_items
from apps.akaunting.core.reconciliations import create_generated_reconciliations
from apps.akaunting.core.setup import setup_akaunting
from apps.akaunting.core.taxes import import_taxes
from apps.akaunting.core.transfers import create_generated_transfers
from apps.akaunting.utils import api
from common.logger import logger


@click.group()
def akaunting_cli():
    pass


@akaunting_cli.command()
def up():
    """Run docker compose up in the docker directory"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    logger.info(f"Running docker compose up in {docker_dir}")
    subprocess.run(["docker", "compose", "up"], cwd=docker_dir)
    logger.info("Akaunting is up and running")


@akaunting_cli.command()
@click.option("--volumes", is_flag=True, help="Remove volumes as well (deletes all data)")
@click.option("--force", is_flag=True, help="Force remove everything including orphaned containers and prune volumes")
def down(volumes: bool, force: bool):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    if volumes:
        cmd.append("--volumes")
    subprocess.run(cmd, cwd=docker_dir)

    # If force is specified, also prune volumes to ensure complete cleanup
    if force:
        print("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"])


@akaunting_cli.command()
@click.option("--n-customers", type=int, default=50, help="Number of customers to create")
@click.option("--n-vendors", type=int, default=50, help="Number of vendors to create")
@click.option("--n-categories", type=int, default=20, help="Number of categories to create")
@click.option("--n-items", type=int, default=80, help="Number of items to create")
@click.option("--n-invoices", type=int, default=150, help="Number of invoices to create")
@click.option("--n-bills", type=int, default=50, help="Number of bills to create")
@click.option("--n-transfers", type=int, default=50, help="Number of transfers to create")
@click.option("--n-reconciliations", type=int, default=50, help="Number of reconciliations to create")
def seed(n_customers, n_vendors, n_categories, n_items, n_invoices, n_bills, n_transfers, n_reconciliations):
    """Seed the database with data"""

    async def async_seed():
        await setup_akaunting()
        await import_taxes()
        await import_currencies()
        await import_payment_accounts()
        await create_customers(n_customers)
        await create_vendors(n_vendors)
        await create_generated_categories(n_categories)
        await create_generated_items(n_items)
        await create_generated_invoices(n_invoices)
        await create_generated_bills(n_bills)
        await create_generated_transfers(n_transfers)
        await create_generated_reconciliations(n_reconciliations)

        await api.close()

    asyncio.run(async_seed())
