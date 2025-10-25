"""Utility functions for ownCloud file operations."""

import os
from pathlib import Path


def get_file_mappings(local_base_path: str) -> list[tuple[str, str]]:
    """
    Get mappings of local file paths to ownCloud upload paths.

        Args:
        local_base_path: Base directory path (relative to src directory)

    Returns:
        List of tuples (local_path, owncloud_path)
    """
    # Get absolute path - we run from seed/src directory
    current_dir = Path.cwd()  # This is seed/src
    local_path = current_dir / local_base_path

    if not local_path.exists():
        raise FileNotFoundError(f"Directory not found: {local_path}")

    mappings = []

    # Walk through all files in the directory
    for root, _, files in os.walk(local_path):
        root_path = Path(root)

        # Calculate relative path from the base directory
        relative_root = root_path.relative_to(local_path)

        # Create ownCloud path (using files/admin/ prefix for WebDAV)
        owncloud_base = "files/admin" if str(relative_root) == "." else f"files/admin/{relative_root.as_posix()}"

        # Add directory creation mapping (for non-root directories)
        if str(relative_root) != ".":
            mappings.append((str(root_path), owncloud_base))

        # Add file mappings
        for file in files:
            local_file_path = root_path / file
            owncloud_file_path = f"{owncloud_base}/{file}"
            mappings.append((str(local_file_path), owncloud_file_path))

    return mappings


def get_directory_structure(local_base_path: str) -> list[str]:
    """
    Get list of directories that need to be created in ownCloud.

        Args:
        local_base_path: Base directory path (relative to src directory)

    Returns:
        List of ownCloud directory paths to create
    """
    current_dir = Path.cwd()  # This is seed/src
    local_path = current_dir / local_base_path

    if not local_path.exists():
        raise FileNotFoundError(f"Directory not found: {local_path}")

    directories = []

    # Walk through all directories
    for root, _, _ in os.walk(local_path):
        root_path = Path(root)
        relative_root = root_path.relative_to(local_path)

        # Skip root directory
        if str(relative_root) == ".":
            continue

        # Create ownCloud directory path
        owncloud_dir = f"files/admin/{relative_root.as_posix()}"
        directories.append(owncloud_dir)

    return directories


def is_file_path(path: str) -> bool:
    """
    Check if a path represents a file (vs directory).

    Args:
        path: File path to check

    Returns:
        True if it's a file, False if it's a directory
    """
    return Path(path).is_file()
