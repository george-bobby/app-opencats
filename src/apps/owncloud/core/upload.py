"""ownCloud WebDAV upload functionality."""

import base64
import os
from pathlib import Path

import httpx

from common.logger import logger

from ..utils.utils import get_directory_structure, get_file_mappings, is_file_path


def get_basic_auth_header() -> str:
    """Generate Basic Auth header for ownCloud."""
    user = os.getenv("OCIS_USER", "admin")
    pwd = os.getenv("OCIS_PASS", "admin")
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {token}"


def build_webdav_url(path: str) -> str:
    """Build WebDAV URL for ownCloud."""
    base_url = os.getenv("OCIS_URL", "https://localhost:9200")
    # Remove leading slash if present
    if path.startswith("/"):
        path = path[1:]
    return f"{base_url}/remote.php/dav/{path}"


async def create_directory(owncloud_path: str) -> bool:
    """
    Create a directory in ownCloud using WebDAV MKCOL.

    Args:
        owncloud_path: ownCloud directory path (e.g., 'files/admin/folder')

    Returns:
        True if successful, False otherwise
    """
    headers = {"Authorization": get_basic_auth_header()}
    url = build_webdav_url(owncloud_path)

    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.request("MKCOL", url, headers=headers)
            resp.raise_for_status()

        logger.info(f"Created directory: {owncloud_path}")
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 405:  # Method Not Allowed - directory already exists
            logger.debug(f"Directory already exists: {owncloud_path}")
            return True
        else:
            logger.error(f"Failed to create directory {owncloud_path}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error creating directory {owncloud_path}: {e}")
        return False


async def upload_to_owncloud(local_path: str, owncloud_path: str) -> bool:
    """
    Upload a file to ownCloud using WebDAV PUT.

    Args:
        local_path: Local file path
        owncloud_path: ownCloud file path (e.g., 'files/admin/file.txt')

    Returns:
        True if successful, False otherwise
    """
    local_file = Path(local_path)
    if not local_file.exists():
        logger.error(f"Local file not found: {local_path}")
        return False

    headers = {"Authorization": get_basic_auth_header()}
    url = build_webdav_url(owncloud_path)

    try:
        with local_file.open("rb") as f:
            file_content = f.read()

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.put(url, headers=headers, content=file_content)
            resp.raise_for_status()

        file_size = local_file.stat().st_size
        logger.info(f"Uploaded {local_path} -> {owncloud_path} ({file_size} bytes)")
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to upload {local_path}: HTTP {e.response.status_code}")
        return False
    except Exception as e:
        logger.error(f"Error uploading {local_path}: {e}")
        return False


async def upload(local_base_path: str) -> None:
    """
    Master function to upload files and directories to ownCloud.

    Args:
        local_base_path: Base directory path (relative to src directory)
    """
    logger.start(f"Starting upload from {local_base_path}")

    try:
        # Get directory structure and file mappings
        directories = get_directory_structure(local_base_path)
        file_mappings = get_file_mappings(local_base_path)

        # Filter out directories from file mappings
        file_only_mappings = [(local, remote) for local, remote in file_mappings if is_file_path(local)]

        logger.info(f"Found {len(directories)} directories and {len(file_only_mappings)} files")

        # Create directories first
        for directory in directories:
            await create_directory(directory)

        # Upload files
        success_count = 0
        for local_path, owncloud_path in file_only_mappings:
            if await upload_to_owncloud(local_path, owncloud_path):
                success_count += 1

        if success_count == len(file_only_mappings):
            logger.succeed(f"Successfully uploaded all {success_count} files")
        else:
            failed_count = len(file_only_mappings) - success_count
            logger.warning(f"Uploaded {success_count} files, {failed_count} failed")

    except FileNotFoundError as e:
        logger.error(str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
