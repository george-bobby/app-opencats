import asyncio
import subprocess
from pathlib import Path

import click

from apps.frappecrm.core import contacts, deals, desk, emails, leads, notes, organizations, users
from common.logger import logger


@click.group()
def frappecrm_cli():
    pass


@frappecrm_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
@click.option("--build", is_flag=True, help="Build the docker image")
def up(detach: bool, build: bool):
    """Run docker compose up in the docker directory"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")
    if build:
        cmd.append("--build")
    subprocess.run(cmd, cwd=docker_dir)


@frappecrm_cli.command()
@click.option("-v", "--volumes", is_flag=True, help="Remove volumes as well (deletes all data)")
@click.option("-f", "--force", is_flag=True, help="Force remove everything including orphaned containers and prune volumes")
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


@frappecrm_cli.command()
@click.option("--n-organizations", type=int, default=100, help="Number of organizations to generate")
@click.option("--n-email-templates", type=int, default=10, help="Number of email templates to generate")
@click.option("--n-leads", type=int, default=200, help="Number of leads to generate")
@click.option("--n-notes", type=int, default=50, help="Number of notes to generate")
def generate(n_organizations: int, n_email_templates: int, n_leads: int, n_notes: int):
    """Generate data using LLMs and save to JSON files"""

    async def async_generate():
        logger.start("Generating users...")
        await users.generate_users(20)
        logger.succeed("Generated users")

        logger.start(f"Generating {n_organizations} organizations...")
        await organizations.generate_organizations(n_organizations)
        logger.succeed(f"Generated {n_organizations} organizations")

        logger.start("Generating contacts...")
        await contacts.generate_contacts(contacts_per_org=(1, 3))
        logger.succeed("Generated contacts")

        logger.start(f"Generating {n_email_templates} email templates...")
        await emails.generate_email_templates(n_email_templates)
        logger.succeed(f"Generated {n_email_templates} email templates")

        logger.start(f"Generating {n_leads} leads...")
        await leads.generate_leads(n_leads)
        logger.succeed(f"Generated {n_leads} leads")

        logger.start("Generating lead content...")
        await leads.generate_content(
            number_of_leads=n_leads,
            emails_per_lead=(1, 5),
            notes_per_lead=(1, 5),
            tasks_per_lead=(2, 5),
            comments_per_lead=(2, 5),
        )
        logger.succeed("Generated lead content")

        logger.start(f"Generating {n_notes} notes...")
        await notes.generate_notes(n_notes)
        logger.succeed(f"Generated {n_notes} notes")

    asyncio.run(async_generate())


@frappecrm_cli.command()
@click.option("--n-organizations", type=int, default=100, help="Number of organizations to insert")
@click.option("--n-email-templates", type=int, default=10, help="Number of email templates to insert")
@click.option("--n-leads", type=int, default=182, help="Number of leads to insert")  # defaulting to 182 because thats how many leads are in the generated leads.json file
@click.option("--n-deals", type=int, default=100, help="Number of deals to insert")
def seed(n_organizations: int, n_email_templates: int, n_leads: int, n_deals: int):
    """Insert data from JSON files into the CRM system"""

    async def async_seed():
        await desk.setup_site()
        await users.insert_users()
        await organizations.insert_organizations(n_organizations)
        await contacts.insert_addresses()
        await contacts.insert_contacts()
        await contacts.update_empty_contacts()
        await emails.insert_email_templates(n_email_templates)
        await leads.insert_leads(n_leads)
        await leads.add_calls(number_of_leads=n_leads, calls_per_lead=(1, 3))
        await leads.add_content(number_of_leads=n_leads)
        await leads.convert_to_deals(
            n_deals
        )  # Note: converted leads do not show up in the "leads" page because leads with `converted=1` are filtered out: https://github.com/deeptuneai/app-frappecrm/blob/deeptune/v1.52.9/frontend/src/pages/Leads.vue#L26
        await deals.randomize_deal_status(n_deals)

    asyncio.run(async_seed())
