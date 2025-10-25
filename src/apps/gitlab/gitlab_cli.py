import os
import subprocess
import time
from pathlib import Path

import click
import requests

from apps.gitlab.config.settings import get_db_config, load_config, settings
from apps.gitlab.core.comprehensive_importer import ComprehensiveImporter
from apps.gitlab.core.fix_create_user_name import DirectDBImportUserFixer
from apps.gitlab.core.fix_project_member import ProjectMemberDistributor
from common.logger import logger


@click.group()
def gitlab_cli():
    pass


@gitlab_cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in detached mode")
def up(detach: bool):
    """Run docker compose up in the docker directory and create database"""

    # Set environment variables from settings.py
    os.environ["GITLAB_TOKEN"] = settings.GITLAB_TOKEN
    os.environ["GITHUB_TOKEN"] = settings.GITHUB_TOKEN
    os.environ["DEBUG"] = str(settings.DEBUG).lower()

    # Start docker containers
    docker_dir = Path(__file__).parent.joinpath("docker")
    cmd = ["docker", "compose", "up", "--build"]
    if detach:
        cmd.append("-d")

    subprocess.run(cmd, cwd=docker_dir)


@gitlab_cli.command()
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
        logger.warning("Force cleanup: removing all unused volumes...")
        subprocess.run(["docker", "volume", "prune", "-f"])


@gitlab_cli.command()
@click.option("--repo", type=str, help="Import specific repository")
@click.option("--advanced-attribution", is_flag=True, default=True, help="Use advanced attribution")
def seed(repo: str, advanced_attribution: bool):
    """
    Import GitHub repositories to GitLab with automatic post-import fixes.

    This command performs a complete seeding workflow:
    1. Import repositories from GitHub to GitLab
    2. Automatically run post-import fixes to ensure data integrity

    The post-import fixes are essential because:
    - GitLab's import process creates issues/MRs with a generic "Import User"
    - Project members need proper distribution for realistic data
    - These fixes ensure the imported data appears authentic and usable
    """

    # Get repository configuration
    config = load_config()
    if not config:
        logger.fail("No repositories configured in settings.py")
        return

    # Import specific repo or all repos
    repos_to_import = {repo: config[repo]} if repo and repo in config else config

    if repo and repo not in config:
        logger.fail(f"Repository '{repo}' not found in settings")
        return

    # Phase 1: Import repositories
    logger.info("🚀 Starting GitLab seeding process...")
    logger.info("Phase 1: Importing repositories from GitHub")

    successful_imports = []
    failed_imports = []

    for repo_name, repo_url in repos_to_import.items():
        logger.start(f"Importing {repo_name}...")
        try:
            importer = ComprehensiveImporter(advanced_attribution=advanced_attribution)
            result = importer.import_repository_comprehensive(repo_name, repo_url)
            if result:
                logger.succeed(f"{repo_name} imported successfully")
                successful_imports.append(repo_name)
            else:
                logger.fail(f"{repo_name} import failed")
                failed_imports.append(repo_name)
        except Exception as e:
            logger.fail(f"Error importing {repo_name}: {e}")
            failed_imports.append(repo_name)

    # Phase 2: Automatic post-import fixes
    if successful_imports:
        logger.info(f"\nPhase 2: Running automatic post-import fixes for {len(successful_imports)} repositories")
        logger.info("These fixes are essential for data integrity and realistic seeding:")
        logger.info("• Fix project member distribution - ensures proper access levels")
        logger.info("• Fix import user attribution - replaces generic import user with actual members")

        _run_automatic_fixes()

    # Summary
    logger.info("\n✅ Seeding completed!")
    logger.info(f"• Successfully imported: {len(successful_imports)} repositories")
    if failed_imports:
        logger.warning(f"• Failed imports: {len(failed_imports)} repositories: {', '.join(failed_imports)}")
    if successful_imports:
        logger.info("• Post-import fixes applied automatically")


def _run_automatic_fixes():
    """
    Run essential post-import fixes automatically.

    These fixes are critical for proper GitLab seeding because:

    1. PROJECT MEMBER DISTRIBUTION FIX:
       - GitLab imports don't automatically assign proper project members
       - Without this fix, projects would have minimal or no members
       - This distributes users across projects with appropriate access levels
       - Ensures realistic project collaboration scenarios

    2. IMPORT USER ATTRIBUTION FIX:
       - GitLab's import process creates all issues/MRs under a generic "Import User"
       - This makes the data look artificial and unrealistic
       - The fix reassigns authorship to actual project members
       - Creates authentic-looking contribution history
       - Essential for testing user-based features and analytics

    Both fixes run automatically because they are prerequisites for a functional
    GitLab environment with realistic, usable data.
    """

    # Fix 1: Distribute project members
    logger.start("Running project member distribution fix...")
    logger.info("→ This ensures projects have proper member access levels")
    try:
        distributor = ProjectMemberDistributor()
        distributor.run(access_level=30, debug_mode=False)
        logger.succeed("Project member distribution completed successfully")
    except Exception as e:
        logger.fail(f"Project member distribution failed: {e}")
        logger.warning("Continuing with import user fix despite member distribution failure")

    # Fix 2: Fix import user attribution
    logger.start("Running import user attribution fix...")
    logger.info("→ This replaces generic 'Import User' with actual project members")
    try:
        # Get database configuration from settings
        db_config = get_db_config()

        logger.info("Using database configuration:")
        logger.info(f"   host={db_config['host']}, database={db_config['database']}, user={db_config['user']}")

        fixer = DirectDBImportUserFixer(db_config)
        # Execute actual changes (not dry run)
        fixer.run(dry_run=False)

        logger.succeed("Import user attribution fix completed successfully")

    except Exception as e:
        logger.fail(f"Import user attribution fix failed: {e}")
        logger.warning("Some imported content may still show 'Import User' as author")

    logger.info("✅ All automatic post-import fixes completed")


@gitlab_cli.command("fix-members")
def fix_members():
    """Manually run project member distribution fix (normally runs automatically during seed)"""
    logger.info("Running manual project member distribution fix...")
    logger.warning("Note: This normally runs automatically as part of the seed command")

    try:
        distributor = ProjectMemberDistributor()
        distributor.run(access_level=30, debug_mode=False)
        logger.succeed("Project member distribution completed successfully")
    except Exception as e:
        logger.fail(f"Project member distribution failed: {e}")


@gitlab_cli.command("fix-create-user-name")
def fix_create_user_name():
    """Manually run import create user name fix (normally runs automatically during seed)"""
    logger.info("Running manual import create user name fix...")
    logger.warning("Note: This normally runs automatically as part of the seed command")

    try:
        db_config = get_db_config()
        logger.info("Using database configuration:")
        logger.info(f"   host={db_config['host']}, database={db_config['database']}, user={db_config['user']}")

        fixer = DirectDBImportUserFixer(db_config)
        fixer.run(dry_run=False)
        logger.succeed("Import create user name fix completed successfully")
    except Exception as e:
        logger.fail(f"Import create user name fix failed: {e}")


@gitlab_cli.command("status")
def status():
    """Check GitLab container status and readiness"""
    result = _check_gitlab_status()
    if result:
        click.echo("✅ GitLab is running and accessible at http://localhost")
    else:
        click.echo("❌ GitLab is not accessible at http://localhost")
    return result


def _check_gitlab_status():
    """Check if GitLab is accessible"""
    url = "http://localhost"
    max_retries = 30
    retry_delay = 2

    click.echo("Checking GitLab status at http://localhost...")

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code in [200, 302]:
                click.echo(f"✅ GitLab responded with status code: {response.status_code}")
                return True

        except requests.exceptions.ConnectionError:
            click.echo(f"⏳ Attempt {attempt + 1}/{max_retries}: Connection refused, retrying...")
        except requests.exceptions.Timeout:
            click.echo(f"⏳ Attempt {attempt + 1}/{max_retries}: Timeout, retrying...")
        except Exception as e:
            click.echo(f"⏳ Attempt {attempt + 1}/{max_retries}: Error - {e}")

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    click.echo("❌ GitLab failed to respond after all attempts")
    return False


if __name__ == "__main__":
    gitlab_cli()
