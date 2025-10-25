import asyncio
import subprocess
from pathlib import Path

import click

from apps.owncloud.core.upload import upload
from common.logger import logger


@click.group()
def owncloud_cli():
    """ownCloud management commands"""
    pass


@owncloud_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Start ownCloud services"""
    logger.start("Starting ownCloud services...")

    docker_dir = Path(__file__).parent.joinpath("docker")

    # Check if ocis.yaml config exists, if not, initialize it
    ocis_config = docker_dir.joinpath("ocis.yaml")
    if not ocis_config.exists():
        logger.info("oCIS config not found, initializing...")
        try:
            subprocess.run(["docker", "run", "--rm", "-it", "-v", f"{docker_dir}:/etc/ocis/", "owncloud/ocis:latest", "init"], check=True, cwd=docker_dir)
            logger.succeed("oCIS initialized successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize oCIS: {e}")
            raise

    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")

    try:
        subprocess.run(cmd, check=True, cwd=docker_dir)
        if detach:
            logger.succeed("ownCloud services started in detached mode")
            logger.info("Access ownCloud at: https://localhost:9200")
            logger.info("Default credentials - Username: admin, Password: admin")
        else:
            logger.succeed("ownCloud services started")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start ownCloud services: {e}")
        raise


@owncloud_cli.command()
def down():
    """Stop ownCloud services and cleanup"""
    logger.start("Stopping ownCloud services...")

    docker_dir = Path(__file__).parent.joinpath("docker")

    try:
        # Stop and remove containers, networks, volumes
        subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], check=True, cwd=docker_dir)

        logger.succeed("ownCloud services stopped and cleaned up")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop ownCloud services: {e}")
        raise


@owncloud_cli.command()
@click.option("--path", required=True, help="Local directory path to upload (relative to src directory) apps/owncloud/data/default/hr")
def seed(path: str):
    """Upload files and directories to ownCloud"""

    async def async_seed():
        await upload(path)

    asyncio.run(async_seed())


if __name__ == "__main__":
    owncloud_cli()
