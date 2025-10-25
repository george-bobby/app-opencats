import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.chatwoot.config.settings import settings
from apps.chatwoot.core.agents import generate_agents, seed_agents, update_agent_statues
from apps.chatwoot.core.automations import generate_automations, seed_automations
from apps.chatwoot.core.campaigns import generate_campaigns, seed_campaigns
from apps.chatwoot.core.canned_responses import generate_canned_responses, seed_canned_responses
from apps.chatwoot.core.contacts import generate_contacts, seed_contacts
from apps.chatwoot.core.conversations import fix_message_status, generate_conversations, seed_conversations
from apps.chatwoot.core.custom_attributes import generate_custom_attributes, seed_custom_attributes
from apps.chatwoot.core.inboxes import generate_inboxes, seed_inboxes
from apps.chatwoot.core.labels import generate_labels, seed_labels
from apps.chatwoot.core.macros import generate_macros, seed_macros
from apps.chatwoot.core.onboarding import setup_onboarding
from apps.chatwoot.core.reports import fix_converstion_timestamps
from apps.chatwoot.core.teams import generate_teams, seed_teams
from common.logger import logger


@click.group()
def chatwoot_cli():
    pass


@chatwoot_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    logger.debug("Preparing database...")
    subprocess.run(["docker", "compose", "run", "--rm", "rails", "bundle", "exec", "rails", "db:chatwoot_prepare"], cwd=docker_dir, env=env)

    logger.debug("Starting services...")
    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")
    subprocess.run(cmd, cwd=docker_dir, env=env)


@chatwoot_cli.command()
def down():
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}

    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(cmd, cwd=docker_dir, env=env)

    print("Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"])


@chatwoot_cli.command()
def seed():
    """Seed the database with data from JSON files"""

    async def async_seed():
        await setup_onboarding()
        await seed_agents()
        await update_agent_statues()
        await seed_teams()
        await seed_inboxes()
        await seed_labels()
        await seed_custom_attributes()
        await seed_canned_responses()
        await seed_contacts()
        await seed_campaigns()
        await seed_macros()
        await seed_automations()
        await seed_conversations()
        await fix_message_status()
        await fix_converstion_timestamps()

    asyncio.run(async_seed())


@chatwoot_cli.command()
@click.option("--agents", type=int, default=50, help="Number of agents to generate")
@click.option("--teams", type=int, default=8, help="Number of teams to generate")
@click.option("--inboxes", type=int, default=50, help="Number of inboxes to generate")
@click.option("--labels", type=int, default=35, help="Number of labels to generate")
@click.option("--custom-attributes", type=int, default=10, help="Number of custom attributes to generate")
@click.option("--canned-responses", type=int, default=30, help="Number of canned responses to generate")
@click.option("--contacts", type=int, default=2000, help="Number of contacts to generate")
@click.option("--campaigns", type=int, default=15, help="Number of campaigns to generate")
@click.option("--macros", type=int, default=15, help="Number of macros to generate")
@click.option("--automations", type=int, default=15, help="Number of automations to generate")
@click.option("--conversations", type=int, default=1000, help="Number of conversations to generate")
def generate(
    agents: int,
    teams: int,
    inboxes: int,
    labels: int,
    custom_attributes: int,
    canned_responses: int,
    contacts: int,
    campaigns: int,
    macros: int,
    automations: int,
    conversations: int,
):
    """Generate data for Chatwoot"""

    async def async_generate():
        await generate_agents(agents)
        await asyncio.gather(
            generate_inboxes(inboxes),
            generate_teams(teams),
            generate_labels(labels),
            generate_custom_attributes(custom_attributes),
            generate_canned_responses(canned_responses),
            generate_campaigns(campaigns),
            generate_contacts(contacts),
            generate_macros(macros),
        )
        await asyncio.gather(
            generate_automations(automations),
            generate_conversations(conversations),
        )

    asyncio.run(async_generate())
