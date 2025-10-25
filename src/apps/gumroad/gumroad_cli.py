import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.gumroad.config.settings import settings
from apps.gumroad.core.analytics import backfill_all_purchases, delete_all_indices_and_reindex_all, generate_product_views, seed_product_views
from apps.gumroad.core.audiences import generate_followers
from apps.gumroad.core.checkout import generate_discounts, seed_discounts, update_checkout_form
from apps.gumroad.core.emails import generate_emails, seed_emails
from apps.gumroad.core.payouts import generate_payouts, seed_payouts
from apps.gumroad.core.products import generate_products, seed_products
from apps.gumroad.core.sales import generate_sales, seed_sales
from apps.gumroad.core.settings import setup_profile
from apps.gumroad.core.workflows import generate_workflows, seed_workflows
from common.logger import logger


@click.group()
def gumroad_cli():
    pass


@gumroad_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
@click.option("--build", is_flag=True, help="Build the docker image")
def up(detach: bool, build: bool):
    """Run docker compose up in the docker directory"""
    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")

    if build:
        cmd.append("--build")

    subprocess.run(cmd, cwd=docker_dir, env=env)


@gumroad_cli.command()
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
        logger.info("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"])


@gumroad_cli.command()
def seed():
    async def async_seed_gumroad():
        try:
            await setup_profile()
            await seed_products()
            await seed_discounts()
            await update_checkout_form()
            await seed_workflows()
            await seed_emails()
            await seed_sales()
            await backfill_all_purchases()
            await delete_all_indices_and_reindex_all()
            await seed_product_views()
            await seed_payouts()
        finally:
            pass

    asyncio.run(async_seed_gumroad())


@gumroad_cli.command()
@click.option("-p", "--products", type=int, default=15, help="Number of products to generate")
@click.option("-d", "--discounts", type=int, default=20, help="Number of discounts to generate")
@click.option("-w", "--workflows", type=int, default=5, help="Number of workflows to generate")
@click.option("-e", "--emails", type=int, default=10, help="Number of emails to generate")
@click.option("-s", "--sales", type=int, default=500, help="Number of sales to generate")
@click.option("-f", "--followers", type=int, default=2000, help="Number of followers to generate")
@click.option("-v", "--views", type=int, default=20000, help="Number of product views to generate")
@click.option("-p", "--payouts", type=int, default=24, help="Number of payouts to generate")
def generate(products: int, discounts: int, workflows: int, emails: int, sales: int, followers: int, views: int, payouts: int):
    async def async_generate_gumroad():
        try:
            await generate_product_views(views)
            await generate_products(products)
            await generate_discounts(discounts)
            await generate_workflows(workflows)
            await generate_emails(emails)
            await generate_sales(sales)
            await generate_followers(followers)
            await generate_product_views(views)
            await generate_payouts(payouts)
        finally:
            pass

    asyncio.run(async_generate_gumroad())
