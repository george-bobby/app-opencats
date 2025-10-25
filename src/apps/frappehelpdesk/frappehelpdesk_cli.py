import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.core.canned_responses import generate_canned_responses, seed_canned_responses
from apps.frappehelpdesk.core.customers import generate_customer_users, generate_customers, seed_customer_users, seed_customers
from apps.frappehelpdesk.core.desk import setup_site
from apps.frappehelpdesk.core.knowledge_base import generate_kb_articles, generate_kb_categories, seed_kb_articles, seed_kb_categories
from apps.frappehelpdesk.core.teams import delete_teams, generate_team_assignments, generate_teams, seed_team_assignments, seed_teams
from apps.frappehelpdesk.core.tickets import generate_tickets, seed_tickets
from apps.frappehelpdesk.core.users import generate_users, seed_users


@click.group()
def frappehelpdesk_cli():
    pass


@frappehelpdesk_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""
    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir, env=env)


@frappehelpdesk_cli.command()
@click.option("-v", "--volumes", is_flag=True, help="Remove volumes as well (deletes all data)")
@click.option("-f", "--force", is_flag=True, help="Force remove everything including orphaned containers and prune volumes")
def down(volumes: bool, force: bool):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans"]
    if volumes:
        cmd.append("--volumes")
    subprocess.run(cmd, cwd=docker_dir, env=env)

    # If force is specified, also prune volumes to ensure complete cleanup
    if force:
        print("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"], env=env)


@frappehelpdesk_cli.command()
@click.option("--agents", type=int, default=40, help="Number of users to insert")
@click.option("--admins", type=int, default=10, help="Number of admins to insert")
@click.option("--customers", type=int, default=500, help="Number of customers to insert")
@click.option("--customer-users", type=int, default=100, help="Number of customer users to insert")
@click.option("--teams", type=int, default=5, help="Number of teams to generate")
@click.option("--tickets", type=int, default=300, help="Number of tickets to insert")
@click.option("--tickets-per-batch", type=int, default=100, help="Number of tickets to generate per batch")
@click.option("--kb-categories", type=int, default=10, help="Number of knowledge base categories to generate")
@click.option("--kb-articles", type=int, default=100, help="Number of knowledge base articles to generate")
@click.option("--canned-responses", type=int, default=50, help="Number of canned responses to generate")
def generate(agents: int, admins: int, customers: int, customer_users: int, teams: int, tickets: int, tickets_per_batch: int, kb_categories: int, kb_articles: int, canned_responses: int):
    """Generate data using LLMs and save to JSON files"""

    async def async_generate():
        await generate_users(agents, admins)
        await generate_customers(customers)
        await generate_customer_users(customer_users)
        await asyncio.gather(
            generate_teams(teams),
            generate_kb_categories(kb_categories),
        )
        await generate_team_assignments()
        await asyncio.gather(
            generate_kb_articles(kb_articles),
            generate_canned_responses(canned_responses),
            generate_tickets(tickets, tickets_per_batch),
        )

    asyncio.run(async_generate())


@frappehelpdesk_cli.command()
def seed():
    """Insert data from JSON files into the HRMS system"""

    async def async_seed():
        """Setup"""
        await setup_site()
        await seed_users()

        """Teams"""
        await delete_teams()
        await seed_teams()
        await seed_team_assignments()

        """Customers"""
        await seed_customers()
        await seed_customer_users()

        """Knowledge Bases"""
        await seed_kb_categories()
        await seed_kb_articles()

        """Canned Responses"""
        await seed_canned_responses()

        """Tickets"""
        await seed_tickets()

    asyncio.run(async_seed())
