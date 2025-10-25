import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.spree.config.settings import settings
from apps.spree.core.images import seed_images_for_products
from apps.spree.core.inventory_units import generate_inventory_units, seed_inventory_units
from apps.spree.core.menus import generate_menus, seed_menus
from apps.spree.core.option_types import generate_option_types, seed_option_types
from apps.spree.core.orders import generate_orders, seed_orders
from apps.spree.core.pages import generate_pages, seed_pages
from apps.spree.core.payments import generate_payment_methods, seed_payment_methods
from apps.spree.core.products import generate_products, seed_products
from apps.spree.core.promotions import generate_promotion_categories, generate_promotions, seed_promotion_categories, seed_promotions
from apps.spree.core.properties import generate_properties, seed_properties
from apps.spree.core.prototypes import generate_prototypes, seed_prototypes
from apps.spree.core.refunds import generate_refund_reasons, seed_refund_reasons
from apps.spree.core.reimbursements import generate_reimbursements, seed_reimbursements
from apps.spree.core.returns import (
    fix_customer_returns,
    generate_customer_returns,
    generate_rma_reasons,
    generate_rmas,
    seed_customer_returns,
    seed_rma_reasons,
    seed_rmas,
)
from apps.spree.core.roles import seed_roles
from apps.spree.core.setup import setup_spree
from apps.spree.core.shipping import generate_shipping_methods, seed_shipping_methods
from apps.spree.core.stock_items import generate_stock_items, seed_stock_items
from apps.spree.core.stock_locations import generate_stock_locations, seed_stock_locations
from apps.spree.core.stock_transfers import generate_stock_transfers, seed_stock_transfers
from apps.spree.core.taxes import generate_tax_categories, generate_tax_rates, seed_tax_categories, seed_tax_rates
from apps.spree.core.taxonomies import generate_taxonomies, seed_taxonomies
from apps.spree.core.taxons import generate_taxons, seed_taxons
from apps.spree.core.users import generate_users, seed_users
from apps.spree.libs.orders.shipping_rates import generate_shipping_rates, seed_shipping_rates
from apps.spree.utils.database import close_db, init_db
from common.logger import logger


@click.group()
def spree_cli():
    pass


@spree_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""
    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(["mkdir", "-p", "storage"], cwd=docker_dir, env=env)
    subprocess.run(cmd, cwd=docker_dir, env=env)


@spree_cli.command()
@click.option("-t", "--timeout", type=int, default=10, help="Timeout in seconds")
def down(timeout: int):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes", f"--timeout={timeout}"]
    env = {**os.environ, **settings.model_dump_str()}

    subprocess.run(cmd, cwd=docker_dir, env=env)

    print("Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])

    # Remove all images
    subprocess.run(["rm", "-rf", "storage"], cwd=docker_dir, env=env)


@spree_cli.command()
@click.option("-f", "--follow", is_flag=True, help="Follow logs")
def logs(follow: bool):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    cmd = ["docker", "compose", "logs"]
    if follow:
        cmd.append("-f")
    subprocess.run(cmd, cwd=docker_dir, env=env)


@spree_cli.command()
def seed():
    """Seed the Spree database with initial data"""

    async def async_seed_spree():
        try:
            await init_db()
            await setup_spree()

            # Base data - no dependencies
            await seed_roles()
            await seed_tax_categories()
            await seed_refund_reasons()
            await seed_rma_reasons()
            await seed_promotion_categories()

            # First level dependencies
            await seed_tax_rates()
            await seed_shipping_methods()
            await seed_payment_methods()
            await seed_users()
            await seed_taxonomies()

            # Second level dependencies
            await seed_taxons()
            await seed_option_types()
            await seed_properties()
            await seed_prototypes()
            await seed_stock_locations()

            # Products and inventory
            await seed_products()
            await seed_images_for_products()
            await seed_stock_items()
            await seed_stock_transfers()

            # Orders and returns flow
            await seed_orders()
            await seed_inventory_units()
            await seed_shipping_rates()
            await seed_promotions()
            await seed_rmas()
            await seed_customer_returns()
            await seed_reimbursements()
            await fix_customer_returns()

            # Content and presentation
            await seed_pages()
            await seed_menus()
        finally:
            await close_db()

    asyncio.run(async_seed_spree())


@spree_cli.command()
@click.option("--taxonomies", default=4, help="Number of taxonomies to generate")
@click.option("--tax-categories", default=9, help="Number of tax categories to generate")
@click.option("--tax-rates", default=12, help="Number of tax rates to generate")
@click.option("--shipping-methods", default=7, help="Number of shipping methods to generate")
@click.option("--refund-reasons", default=9, help="Number of refund reasons to generate")
@click.option("--rma-reasons", default=12, help="Number of return reasons to generate")
@click.option("--payment-methods", default=4, help="Number of payment methods to generate")
@click.option("--dashboard-users", default=12, help="Number of dashboard users to generate")
@click.option("--customer-users", default=100, help="Number of customer users to generate")
@click.option("--min-taxons-per-taxonomy", default=7, help="Minimum number of taxons to generate per taxonomy")
@click.option("--max-taxons-per-taxonomy", default=13, help="Maximum number of taxons to generate per taxonomy")
@click.option("--option-types", default=7, help="Number of option types to generate")
@click.option("--properties", default=9, help="Number of properties to generate")
@click.option("--prototypes", default=11, help="Number of prototypes to generate")
@click.option("--products", default=153, help="Number of products to generate")
@click.option("--stock-locations", default=4, help="Number of stock locations to generate")
@click.option("--pages", default=9, help="Number of CMS pages to generate")
@click.option("--header-menu-items", default=7, help="Number of header menu items to generate")
@click.option("--footer-menu-items", default=12, help="Number of footer menu items to generate")
@click.option("--promotion-categories", default=6, help="Number of promotion categories to generate")
@click.option("--stock-transfers", default=47, help="Number of stock transfers to generate")
@click.option("--promotions", default=11, help="Number of promotions to generate")
@click.option("--orders", default=300, help="Number of orders to generate")
@click.option("--rmas", default=53, help="Number of return authorizations to generate")
@click.option("--rma-cancel-percent", default=27, help="Percentage of RMAs that should be cancelled (0-100)")
@click.option("--customer-returns", default=33, help="Number of customer returns to generate")
@click.option("--stock-multiplier", default=1, help="Multiplier for stock items")
def generate(
    taxonomies: int,
    tax_categories: int,
    tax_rates: int,
    shipping_methods: int,
    refund_reasons: int,
    rma_reasons: int,
    payment_methods: int,
    dashboard_users: int,
    customer_users: int,
    min_taxons_per_taxonomy: int,
    max_taxons_per_taxonomy: int,
    option_types: int,
    properties: int,
    prototypes: int,
    products: int,
    stock_locations: int,
    pages: int,
    header_menu_items: int,
    footer_menu_items: int,
    promotion_categories: int,
    stock_transfers: int,
    promotions: int,
    orders: int,
    rmas: int,
    rma_cancel_percent: int,
    customer_returns: int,
    stock_multiplier: int,
):
    """Generate realistic data for Spree store including menus based on existing taxonomies"""

    async def async_generate_spree():
        try:
            # Base data - no dependencies
            await asyncio.gather(
                generate_users(dashboard_users, customer_users),
                generate_taxonomies(taxonomies),
                generate_tax_categories(tax_categories),
                generate_promotion_categories(promotion_categories),
                generate_refund_reasons(refund_reasons),
                generate_rma_reasons(rma_reasons),
            )

            # First level dependencies
            await asyncio.gather(
                generate_tax_rates(tax_rates),
                generate_shipping_methods(shipping_methods),
                generate_payment_methods(payment_methods),
                generate_taxons(min_taxons_per_taxonomy, max_taxons_per_taxonomy),
            )

            # Second level dependencies
            await asyncio.gather(
                generate_option_types(option_types),
                generate_properties(properties),
                generate_prototypes(prototypes),
                generate_stock_locations(stock_locations),
                generate_promotions(promotions),
            )

            # Products and inventory (includes description generation)
            await generate_products(products)
            await generate_stock_items(stock_multiplier)
            await generate_stock_transfers(stock_transfers)

            # Orders and returns flow
            await generate_orders(orders)
            await generate_inventory_units()
            await generate_shipping_rates()
            await generate_rmas(rmas, cancelled_percentage=rma_cancel_percent / 100.0)
            await generate_customer_returns(customer_returns)
            await generate_reimbursements()

            # Content and presentation
            await generate_pages(pages)
            await generate_menus(header_menu_items, footer_menu_items)
        except Exception as e:
            print(f"❌ Error generating data: {e}")
            raise

    logger.start("Generating data...")
    asyncio.run(async_generate_spree())
    logger.succeed("Generation completed")
