import asyncio
import os
import subprocess
from pathlib import Path

import click

from apps.mattermost.config.settings import settings
from apps.mattermost.core.config import initialize, setup_configuration
from apps.mattermost.core.message import insert_channel_messages
from apps.mattermost.core.messages.channel_messages import generate_channel_messages
from apps.mattermost.core.messages.direct_messages import generate_direct_messages, insert_direct_messages
from apps.mattermost.core.teams import generate_teams, insert_channels, insert_teams
from apps.mattermost.core.users import generate_users, insert_users, insert_users_to_channels, pick_users_for_channels
from common.logger import logger


@click.group()
def mattermost_cli():
    pass


@mattermost_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and create database"""

    # Start docker containers
    docker_dir = Path(__file__).parent.joinpath("docker")
    env = {**os.environ, **settings.model_dump_str()}
    cmd = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.without-nginx.yml", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir, env=env)


@mattermost_cli.command()
@click.option("-t", "--time", type=int, default=10, help="Time to wait for compose down")
def down(time: int):
    """Stop and remove containers, networks, and optionally volumes"""

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Basic down command
    cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes", "--timeout", str(time)]
    env = {**os.environ, **settings.model_dump_str()}
    subprocess.run(cmd, cwd=docker_dir, env=env)

    print("Force cleanup: removing all unused volumes...")
    subprocess.run(["docker", "volume", "prune", "-f"], env=env)


@mattermost_cli.command()
@click.option("-t", "--teams", type=int, default=3, help="Number of teams to generate")
@click.option("-u", "--users", type=int, default=98, help="Number of users to generate")
@click.option("--min-channels-per-team", type=int, default=6, help="Number of channels to generate")
@click.option("--max-channels-per-team", type=int, default=12, help="Number of channels to generate")
@click.option("--min-threads-per-channel", type=int, default=50, help="Number of messages per channel")
@click.option("--max-threads-per-channel", type=int, default=100, help="Number of messages per channel")
@click.option("-d", "--direct-message-inboxes", type=int, default=10, help="Number of direct message channels to generate")
@click.option("-m", "--min-threads-per-dm", type=int, default=20, help="Number of threads per direct message conversation")
@click.option("-M", "--max-threads-per-dm", type=int, default=100, help="Number of threads per direct message conversation")
def generate(
    teams: int,
    users: int,
    min_channels_per_team: int,
    max_channels_per_team: int,
    min_threads_per_channel: int,
    max_threads_per_channel: int,
    direct_message_inboxes: int,
    min_threads_per_dm: int,
    max_threads_per_dm: int,
):
    async def generate_mattermost():
        # await generate_direct_messages(direct_message_inboxes)
        # return
        await generate_teams(teams, users, min_channels_per_team, max_channels_per_team)
        await generate_users(users)
        await pick_users_for_channels()
        logger.start("Generating channel messages and direct messages...")
        await asyncio.gather(
            generate_channel_messages(min_threads_per_channel, max_threads_per_channel),
            generate_direct_messages(direct_message_inboxes, min_threads_per_dm, max_threads_per_dm),
        )

    asyncio.run(generate_mattermost())


@mattermost_cli.command()
def seed():
    async def async_seed_mattermost():
        # await insert_direct_messages()
        # return
        await initialize()
        await setup_configuration()
        await insert_teams()
        await insert_users()
        await insert_channels()
        await insert_users_to_channels()
        await insert_channel_messages()
        await insert_direct_messages()

    asyncio.run(async_seed_mattermost())
