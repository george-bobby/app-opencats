import asyncio
import json
from pathlib import Path
from typing import Any

from apps.gumroad.config.settings import settings
from apps.gumroad.utils.gumroad import GumroadAPI
from common.logger import logger


async def get_profile_settings(
    settings_file: Path = settings.DATA_PATH / "settings.json",
):
    """
    Get profile settings from JSON file
    """
    with Path.open(settings_file) as f:
        settings_data = json.load(f)
    return settings_data.get("profile", {})


async def setup_profile(settings_file: Path = settings.DATA_PATH / "settings.json"):
    """
    Setup user profile on Gumroad by reading settings from JSON file

    Args:
        settings_file: Path to the settings JSON file

    Returns:
        Dict containing the API response
    """
    # Read settings from JSON file
    try:
        with Path.open(settings_file) as f:
            settings_data = json.load(f)
        logger.info(f"Loaded settings from {settings_file}")
    except FileNotFoundError:
        logger.error(f"Settings file not found: {settings_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in settings file: {e}")
        raise

    # Extract profile data
    profile_data = settings_data.get("profile")
    if not profile_data:
        raise ValueError("No 'profile' key found in settings file")

    logger.start(f"Setting up profile for user: {profile_data.get('user', {}).get('username', 'unknown')}")

    # Use the Gumroad API to set the profile (credentials from config)
    async with GumroadAPI() as api:
        logger.info("Connected to Gumroad API and logged in")

        # Get current profile first (optional, for logging)
        try:
            current_profile = await api.get_profile()
            logger.info(f"Current profile status: {current_profile.get('status_code')}")
        except Exception as e:
            logger.warning(f"Could not fetch current profile: {e}")

        # Set the new profile
        result = await api.set_profile(profile_data)

        if result.get("status_code") in [200, 201]:
            logger.succeed("Profile setup completed successfully!")
        else:
            logger.error(f"Profile setup failed with status: {result.get('status_code')}")
            logger.error(f"Error: {result.get('error', 'Unknown error')}")

        return result


async def load_profile_settings(
    settings_file: Path = settings.DATA_PATH / "settings.json",
) -> dict:
    """
    Load profile settings from JSON file

    Args:
        settings_file: Path to the settings JSON file

    Returns:
        Dict containing profile settings
    """
    try:
        with Path.open(settings_file) as f:
            settings_data = json.load(f)
        return settings_data.get("profile", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading settings: {e}")
        raise


async def get_all_taxonomies() -> dict[str, Any]:
    """Get all available taxonomies from the local JSON file"""
    try:
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        taxonomies_path = project_root / "data" / "taxonomies.json"

        with taxonomies_path.open(encoding="utf-8") as f:
            taxonomies = json.load(f)

        return {"success": True, "taxonomies": taxonomies, "status_code": 200}

    except FileNotFoundError:
        return {"error": "Taxonomies file not found", "status_code": 404}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parsing error: {e!s}", "status_code": 400}
    except Exception as e:
        return {"error": f"Failed to load taxonomies: {e!s}", "status_code": 500}


def find_taxonomy_by_slug(slug: str) -> dict[str, Any] | None:
    """Find a taxonomy by its slug"""
    taxonomies_result = asyncio.run(get_all_taxonomies())
    if not taxonomies_result.get("success"):
        return None
    return next(
        (t for t in taxonomies_result.get("taxonomies", []) if t.get("slug") == slug),
        None,
    )


def get_taxonomy_hierarchy(taxonomy_id: int, slug: str) -> dict[str, Any]:
    """Get the full hierarchy for a taxonomy (parent and children)"""
    taxonomies_result = asyncio.run(get_all_taxonomies())
    if not taxonomies_result.get("success"):
        return taxonomies_result

    taxonomies = taxonomies_result.get("taxonomies", [])

    # Find target taxonomy
    if taxonomy_id:
        target = next((t for t in taxonomies if t["id"] == taxonomy_id), None)
    elif slug:
        target = next((t for t in taxonomies if t["slug"] == slug), None)
    else:
        return {"error": "Must provide taxonomy_id or slug", "status_code": 400}

    if not target:
        return {"error": "Taxonomy not found", "status_code": 404}

    # Find parent and children
    parent = next((t for t in taxonomies if t["id"] == target.get("parent_id")), None) if target.get("parent_id") else None
    children = [t for t in taxonomies if t.get("parent_id") == target["id"]]

    return {
        "success": True,
        "taxonomy": target,
        "parent": parent,
        "children": children,
        "status_code": 200,
    }
