import asyncio
import random
import subprocess
from pathlib import Path

import click

from apps.medusa.config.constants import RANDOM_SEED
from apps.medusa.core.add_shipping_options import add_shipping_to_draft_orders
from apps.medusa.core.attributes import seed_product_attributes
from apps.medusa.core.categories import seed_categories
from apps.medusa.core.collections import seed_collections
from apps.medusa.core.convert_draft_orders import convert_draft_orders
from apps.medusa.core.customer_groups import seed_customer_groups
from apps.medusa.core.customers import seed_customers
from apps.medusa.core.delete_existing_categories import delete_existing_categories
from apps.medusa.core.delete_existing_products import delete_existing_products
from apps.medusa.core.delete_existing_stock_location import delete_existing_stock_location
from apps.medusa.core.generate.generate_categories import categories
from apps.medusa.core.generate.generate_collections import collections
from apps.medusa.core.generate.generate_customer_groups import customer_groups
from apps.medusa.core.generate.generate_customers import customers
from apps.medusa.core.generate.generate_orders import orders
from apps.medusa.core.generate.generate_products import products
from apps.medusa.core.generate.generate_promotions import promotions
from apps.medusa.core.generate.generate_tags import tags
from apps.medusa.core.generate.generate_types import types
from apps.medusa.core.generate.products_mapping import products_mapping
from apps.medusa.core.mark_categories_inactive import deactivate_empty_categories
from apps.medusa.core.mark_orders_delivered import mark_orders_as_delivered
from apps.medusa.core.mark_orders_fullfilled import mark_orders_as_fulfilled
from apps.medusa.core.mark_orders_paid import mark_orders_as_paid
from apps.medusa.core.mark_orders_shipped import mark_orders_as_shipped
from apps.medusa.core.orders import seed_orders
from apps.medusa.core.price_lists import seed_price_lists
from apps.medusa.core.product_inventory import seed_product_inventory
from apps.medusa.core.products import seed_products
from apps.medusa.core.promotions import seed_promotions
from apps.medusa.core.region import seed_region
from apps.medusa.core.reservations import seed_reservations
from apps.medusa.core.return_reasons import seed_return_reasons
from apps.medusa.core.sales_channels import seed_sales_channels
from apps.medusa.core.shipping_profiles import seed_shipping_profiles
from apps.medusa.core.stock_location import seed_stock_location
from apps.medusa.core.stock_location_options import seed_stock_location_options
from apps.medusa.core.store import update_store
from apps.medusa.core.tags import seed_tags
from apps.medusa.core.tax_region import seed_tax_region
from apps.medusa.core.types import seed_types
from common.logger import logger


@click.group()
def medusa_cli():
    """Medusa Seeding CLI - Manage Medusa data seeding and Docker operations"""
    pass


@medusa_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and start Medusa services"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    logger.info("🚀 Starting Medusa Docker containers...")
    subprocess.run(cmd, cwd=docker_dir)
    logger.succeed("✅ Medusa containers started successfully!")


@medusa_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    logger.info("🛑 Stopping Medusa Docker containers...")
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir)

    logger.info("🧹 Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])
    logger.succeed("✅ Cleanup completed!")


@medusa_cli.command()
def seed():
    """Seed Medusa with sample data"""

    async def async_seed_medusa():
        """Async function to seed Medusa data"""
        logger.info("🌱 Starting Medusa data seeding...")
        random.seed(RANDOM_SEED)

        await delete_existing_products()
        await delete_existing_categories()
        await delete_existing_stock_location()
        await seed_region()
        await seed_tax_region()
        await seed_return_reasons()
        await seed_sales_channels()
        await seed_shipping_profiles()
        await seed_stock_location()
        await seed_stock_location_options()
        await update_store()
        await seed_types()
        await seed_tags()
        await seed_categories()
        await seed_collections()
        await seed_customers()
        await seed_customer_groups()
        await seed_products()
        await deactivate_empty_categories()
        await seed_product_inventory()
        await seed_reservations()
        await seed_product_attributes()
        await seed_price_lists()
        await seed_promotions()
        await seed_orders()
        await add_shipping_to_draft_orders()
        await convert_draft_orders()
        await mark_orders_as_fulfilled()
        await mark_orders_as_paid()
        await mark_orders_as_shipped()
        await mark_orders_as_delivered()

        logger.succeed("✅ Medusa data seeding completed!")

    asyncio.run(async_seed_medusa())


@medusa_cli.command()
@click.option("--n-customers", type=int, default=1000, help="Number of customers to generate")
@click.option("--n-products", type=int, default=400, help="Number of products to generate")
@click.option("--n-tags", type=int, default=80, help="Number of product tags to generate")
@click.option("--n-types", type=int, default=40, help="Number of product types to generate")
@click.option("--n-collections", type=int, default=25, help="Number of collections to generate")
@click.option("--n-categories", type=int, default=30, help="Number of categories to generate")
@click.option("--n-promotions", type=int, default=30, help="Number of promotions to generate")
def generate(
    n_customers: int,
    n_products: int,
    n_tags: int,
    n_types: int,
    n_collections: int,
    n_categories: int,
    n_promotions: int,
):
    async def async_generate():
        logger.info(f"🎲 Starting Medusa data generation... (customers={n_customers}, products={n_products}")

        await customers(n_customers)
        await customer_groups()
        await tags(n_tags)
        await types(n_types)
        await collections(n_collections)
        await categories(n_categories)
        await products_mapping()
        await products(n_products)
        await promotions(n_promotions)
        await orders()

        logger.succeed("✅ Medusa data generation completed!")

    asyncio.run(async_generate())


if __name__ == "__main__":
    medusa_cli()
