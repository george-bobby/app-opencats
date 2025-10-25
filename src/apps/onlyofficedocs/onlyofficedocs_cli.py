import json
import shutil
import subprocess
from pathlib import Path

import click

from apps.onlyofficedocs.config.settings import settings
from apps.onlyofficedocs.core.files import delete_all_files, download_all_files, get_data_files, get_uploaded_files, upload_file, upload_files
from common.logger import logger


@click.group()
def onlyofficedocs_cli():
    pass


@onlyofficedocs_cli.command()
def up():
    """Start OnlyOffice DocumentServer"""
    docker_dir = Path(__file__).parent / "docker"
    subprocess.run(["bash", str(docker_dir / "run-documentserver.sh")], cwd=docker_dir)


@onlyofficedocs_cli.command()
def down():
    """Stop OnlyOffice DocumentServer"""
    docker_dir = Path(__file__).parent / "docker"
    subprocess.run(["bash", str(docker_dir / "stop-documentserver.sh")], cwd=docker_dir)


@onlyofficedocs_cli.command()
@click.option("--file-path", "-f", help="File path relative to src/")
def seed(file_path: str):
    """Upload files to OnlyOffice"""
    if file_path:
        result = upload_file(file_path)
        if result["success"]:
            logger.succeed(f"{result['file_name']}")
        else:
            logger.error(f"{result['file_name']}: {result['error']}")
    else:
        files = get_data_files()
        upload_files(files)


@onlyofficedocs_cli.command()
def uploads():
    """List all uploaded files in OnlyOffice server"""
    result = get_uploaded_files()

    if result["success"]:
        logger.succeed(f"Uploaded files: {json.dumps(result['files'], indent=2)}")
    else:
        logger.error(f"Failed to get uploaded files: {result['error']}")


@onlyofficedocs_cli.command()
def downloads():
    """Download all files from OnlyOffice server to local downloads folder"""
    # Get uploaded files first
    files_result = get_uploaded_files()
    if not files_result["success"]:
        logger.error(f"Failed to get uploaded files: {files_result['error']}")
        return

    files = files_result["files"]
    if not files:
        logger.info("No files to download")
        return

    # Setup downloads directory (same level as data folder)
    downloads_dir = settings.DATA_PATH.parent / "downloads"

    # Remove and recreate downloads directory
    if downloads_dir.exists():
        shutil.rmtree(downloads_dir)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    # Download all files
    result = download_all_files(files, str(downloads_dir))

    if result["success"]:
        logger.info(f"Downloaded {result['downloaded']} files to {downloads_dir}")
        if result["failed"] > 0:
            logger.warning(f"{result['failed']} files failed to download")
    else:
        logger.error(f"Failed to download files: {result['error']}")


@onlyofficedocs_cli.command()
def delete():
    """Delete all files from OnlyOffice server"""
    # Get uploaded files first
    files_result = get_uploaded_files()
    if not files_result["success"]:
        logger.error(f"Failed to get uploaded files: {files_result['error']}")
        return

    files = files_result["files"]
    if not files:
        logger.info("No files to delete")
        return

    # Delete all files
    result = delete_all_files(files)

    if result["success"]:
        logger.info(f"Deleted {result['deleted']} files from OnlyOffice server")
        if result["failed"] > 0:
            logger.warning(f"{result['failed']} files failed to delete")
    else:
        logger.error(f"Failed to delete files: {result['error']}")
