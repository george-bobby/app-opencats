import subprocess
from pathlib import Path

import click


@click.group()
def superset_cli():
    pass


@superset_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory"""
    docker_dir = Path(__file__).parent.joinpath("docker")

    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir)


@superset_cli.command()
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
