import asyncio
import subprocess
from pathlib import Path

import click

from apps.odoosales.core.activity_plan import insert_activity_plans
from apps.odoosales.core.activity_plan_crm import insert_activity_plans_crm
from apps.odoosales.core.activity_type import insert_activity_types
from apps.odoosales.core.combo import insert_combo_choices
from apps.odoosales.core.contact import insert_banks, insert_contact_tags, insert_contacts, insert_industries
from apps.odoosales.core.delivery import diversify_delivery_statuses, insert_deliveries
from apps.odoosales.core.department import insert_departments
from apps.odoosales.core.employee import insert_employees
from apps.odoosales.core.group import insert_groups
from apps.odoosales.core.industry import insert_industry
from apps.odoosales.core.internal_transfer import diversify_internal_transfer_statuses, insert_internal_transfer
from apps.odoosales.core.invoice import insert_invoices, pay_invoices
from apps.odoosales.core.job_position import insert_job_positions
from apps.odoosales.core.lead import convert_to_opportunity, insert_leads, insert_lost_stage, mark_activities_done
from apps.odoosales.core.lead_mining_request import insert_lead_mining_requests
from apps.odoosales.core.location import insert_locations
from apps.odoosales.core.lost_reason import insert_lost_reasons
from apps.odoosales.core.module import activate_modules
from apps.odoosales.core.on_hand_quantity import update_on_hand_quantity
from apps.odoosales.core.order import insert_orders, insert_orders_to_upsell
from apps.odoosales.core.payment import insert_payment_methods
from apps.odoosales.core.physical_adjustment import insert_physical_adjustments
from apps.odoosales.core.pos import setup_pos_profile
from apps.odoosales.core.pos_note import insert_pos_notes
from apps.odoosales.core.pos_order import insert_pos_orders
from apps.odoosales.core.pos_refund import insert_pos_refunds
from apps.odoosales.core.price_list import insert_price_list
from apps.odoosales.core.product import insert_optional_products, insert_pos_categories, insert_product_attributes, insert_product_categories, insert_product_tags, insert_products
from apps.odoosales.core.quotation import insert_quotations, send_quotations
from apps.odoosales.core.receipts import diversify_receipt_statuses, insert_receipts
from apps.odoosales.core.replenishment import insert_replenishment
from apps.odoosales.core.sale_order_header_footer import insert_sale_order_header_footer
from apps.odoosales.core.sale_tag import insert_sale_tags
from apps.odoosales.core.sale_team import insert_sale_teams
from apps.odoosales.core.scrap_adjustment import diversify_scrap_statuses, insert_scrap_adjustments
from apps.odoosales.core.settings import setup_config
from apps.odoosales.core.skill import insert_skills
from apps.odoosales.core.unit_of_measure import insert_units_of_measure
from apps.odoosales.core.user import insert_users
from apps.odoosales.core.warehouse import insert_warehouses
from apps.odoosales.generators.activity_plan import generate_activity_plans
from apps.odoosales.generators.combo import generate_combos
from apps.odoosales.generators.company import generate_companies
from apps.odoosales.generators.department import generate_departments
from apps.odoosales.generators.emp import generate_employees
from apps.odoosales.generators.individual import generate_individuals
from apps.odoosales.generators.job_position import generate_job_positions
from apps.odoosales.generators.lead import generate_leads
from apps.odoosales.generators.lead_mining_request import generate_lead_mining_requests
from apps.odoosales.generators.note import generate_notes
from apps.odoosales.generators.product import generate_products
from apps.odoosales.generators.quotation import generate_quotations
from apps.odoosales.generators.sale_tag import generate_sale_tags
from apps.odoosales.generators.sale_team import generate_sale_teams
from apps.odoosales.generators.skill import generate_skills
from apps.odoosales.generators.user import generate_users
from apps.odoosales.utils.odoo import create_odoo_db


@click.group()
def odoosales_cli():
    pass


@odoosales_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir)


@odoosales_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""
    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir)

    # If force is specified, also prune volumes to ensure complete cleanup
    subprocess.run(["docker", "volume", "prune", "-f"])


@odoosales_cli.command()
@click.option("--n-plans", type=int, default=10, help="Number of activity plans to generate")
@click.option("--n-users", type=int, default=50, help="Number of activity users to generate")
@click.option("--n-notes", type=int, default=10, help="Number of activity notes to generate")
@click.option("--n-products", type=int, default=30, help="Number of products to generate")
@click.option("--n-combo", type=int, default=15, help="Number of combo to generate")
@click.option("--n-companies", type=int, default=30, help="Number of companies to generate")
@click.option("--n-individuals", type=int, default=30, help="Number of individuals to generate")
@click.option("--n-sale-tags", type=int, default=10, help="Number of sale tags to generate")
@click.option("--n-quotations", type=int, default=200, help="Number of quotations to generate")
@click.option("--n-leads", type=int, default=400, help="Number of leads to generate")
@click.option("--n-sale-teams", type=int, default=5, help="Number of sale teams to generate")
@click.option("--n-lead-mining-requests", type=int, default=5, help="Number of lead mining requests to generate")
@click.option("--n-skills", type=int, default=100, help="Number of skills to generate")
@click.option("--n-jobs", type=int, default=30, help="Number of job positions to generate")
@click.option("--n-departments", type=int, default=7, help="Number of departments to generate")
@click.option("--n-employees", type=int, default=12, help="Number of employees to generate")
def generate(
    n_plans: int,
    n_users: int,
    n_notes: int,
    n_products: int,
    n_combo: int,
    n_companies: int,
    n_individuals: int,
    n_sale_tags: int,
    n_quotations: int,
    n_leads: int,
    n_sale_teams: int,
    n_lead_mining_requests: int,
    n_skills: int,
    n_jobs: int,
    n_departments: int,
    n_employees: int,
):
    async def generate_odoosales():
        await asyncio.gather(
            generate_activity_plans(n_plans),
            generate_users(n_users),
            generate_notes(n_notes),
            generate_companies(n_companies),
            generate_individuals(n_individuals),
            generate_sale_tags(n_sale_tags),
            generate_leads(n_leads),
        )

        await generate_sale_teams(n_sale_teams)

        await generate_lead_mining_requests(n_lead_mining_requests)

        await generate_products(n_products)
        await generate_combos(n_combo)
        await generate_quotations(n_quotations)

        await generate_skills(n_skills)
        await generate_job_positions(n_jobs)
        await generate_departments(n_departments)
        await generate_employees(n_employees)

    asyncio.run(generate_odoosales())


@odoosales_cli.command()
def seed():
    async def async_seed_odoosales():
        await activate_modules()
        await setup_config()
        await setup_pos_profile()

        await insert_warehouses()
        await insert_locations()

        await insert_product_tags()
        await insert_product_attributes()
        await insert_product_categories()
        await insert_pos_categories()
        await insert_products()
        await insert_optional_products()
        await insert_combo_choices()
        await insert_price_list()
        await insert_units_of_measure()
        await update_on_hand_quantity()

        await insert_activity_types()
        await insert_activity_plans()
        await insert_activity_plans_crm()

        await insert_industries()
        await insert_groups()
        await insert_users()
        await insert_contact_tags()
        await insert_banks()
        await insert_contacts()

        await insert_sale_tags()
        await insert_sale_teams()

        await insert_sale_order_header_footer()

        await insert_lost_reasons()
        await insert_lead_mining_requests()
        await insert_lost_stage()
        await insert_leads()
        await convert_to_opportunity()
        await mark_activities_done()

        await insert_quotations()
        await insert_orders()
        await send_quotations()
        await insert_orders_to_upsell()

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

        await insert_invoices()
        await pay_invoices()

        await insert_industry()
        await insert_skills()
        await insert_departments()
        await insert_job_positions()
        await insert_employees()
        await insert_payment_methods()
        await insert_pos_orders()
        await insert_pos_refunds()
        await insert_pos_notes()

    create_odoo_db()
    asyncio.run(async_seed_odoosales())
