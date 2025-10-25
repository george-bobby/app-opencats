import asyncio
import subprocess
from pathlib import Path

import click

from apps.odooinventory.core.bom import insert_bill_of_materials
from apps.odooinventory.core.combo import insert_combo_choices
from apps.odooinventory.core.contact import insert_contact_tags, insert_contacts, insert_industries
from apps.odooinventory.core.delivery import diversify_delivery_statuses, insert_deliveries
from apps.odooinventory.core.internal_transfer import diversify_internal_transfer_statuses, insert_internal_transfer
from apps.odooinventory.core.location import insert_locations
from apps.odooinventory.core.manufacturing_order import diversify_mo_status, insert_manufacturing_orders
from apps.odooinventory.core.module import activate_modules
from apps.odooinventory.core.on_hand_quantity import update_on_hand_quantity
from apps.odooinventory.core.operation_type import insert_operation_types
from apps.odooinventory.core.physical_adjustment import insert_physical_adjustments
from apps.odooinventory.core.product import (
    classify_manufacturing_products,
    insert_components_categories,
    insert_product_attributes,
    insert_product_categories,
    insert_products,
)
from apps.odooinventory.core.product_tag import insert_product_tags
from apps.odooinventory.core.receipt import diversify_receipt_statuses, insert_receipts
from apps.odooinventory.core.replenishment import insert_replenishment
from apps.odooinventory.core.scrap_adjustment import diversify_scrap_statuses, insert_scrap_adjustments
from apps.odooinventory.core.scrap_order import insert_scrap_orders
from apps.odooinventory.core.settings import setup_config
from apps.odooinventory.core.unbuild_order import diversify_unbuild_orders, insert_unbuild_orders
from apps.odooinventory.core.unit_of_measure import insert_units_of_measure
from apps.odooinventory.core.warehouse import insert_warehouses
from apps.odooinventory.core.work_center import insert_work_centers
from apps.odooinventory.generators.bom import generate_bill_of_materials
from apps.odooinventory.generators.combo import generate_combos
from apps.odooinventory.generators.product import generate_products
from apps.odooinventory.generators.work_center import generate_work_centers
from apps.odooinventory.utils.odoo import create_odoo_db


@click.group()
def odooinventory_cli():
    pass


@odooinventory_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and create database"""

    # Start docker containers
    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir)


@odooinventory_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir)

    print("Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])


@odooinventory_cli.command()
@click.option("--n-products", type=int, default=20, help="Number of products to generate")
@click.option("--n-combo", type=int, default=10, help="Number of combo to generate")
@click.option("--n-work-centers", type=int, default=12, help="Number of work centers to generate")
def generate(
    n_products: int,
    n_combo: int,
    n_work_centers: int,
):
    async def generate_odooinventory():
        await generate_products(n_products)
        await generate_combos(n_combo)
        await generate_work_centers(n_work_centers)
        await generate_bill_of_materials()

    asyncio.run(generate_odooinventory())


@odooinventory_cli.command()
def seed():
    async def async_seed_odooinventory():
        await activate_modules()
        await setup_config()

        await insert_warehouses()
        await insert_operation_types()
        await insert_locations()
        await insert_units_of_measure()

        await insert_industries()
        await insert_contact_tags()
        await insert_contacts()

        await insert_product_tags()
        await insert_product_attributes()
        await insert_product_categories()
        await insert_products()
        await insert_combo_choices()
        await update_on_hand_quantity()

        await insert_receipts()
        await diversify_receipt_statuses()
        await insert_deliveries()
        await diversify_delivery_statuses()
        await insert_replenishment()
        await insert_internal_transfer()
        await diversify_internal_transfer_statuses()
        await insert_scrap_adjustments()
        await diversify_scrap_statuses()
        await insert_physical_adjustments()

        await insert_components_categories()
        await insert_work_centers()
        await classify_manufacturing_products()
        await insert_bill_of_materials()
        await insert_manufacturing_orders()
        await diversify_mo_status()
        await insert_unbuild_orders()
        await diversify_unbuild_orders()
        await insert_scrap_orders()
        await diversify_scrap_statuses()

    create_odoo_db()
    asyncio.run(async_seed_odooinventory())
