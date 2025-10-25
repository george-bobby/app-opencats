"""Data utilities for Medusa generators."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common.logger import logger
from common.save_to_json import save_to_json


def load_json_file(filepath: str | Path, default: Any = None) -> Any:
    """Load data from JSON file."""
    filepath = Path(filepath)

    if not filepath.exists():
        if default is not None:
            logger.debug(f"File {filepath} doesn't exist, using default value")
        else:
            logger.warning(f"File {filepath} doesn't exist")
        return default

    try:
        with filepath.open(encoding="utf-8") as f:
            data = json.load(f)
            logger.debug(f"Loaded data from {filepath}")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {filepath}: {e}")
        return default
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return default


def load_existing_data(filepath: Path, unique_fields: list[str] | None = None, track_all: bool = False) -> dict[str, Any]:
    """Load existing data and extract unique identifiers for duplicate prevention."""
    existing_data = load_json_file(filepath, [])

    result = {"used_identifiers": {}, "items": [] if track_all else None, "count": len(existing_data)}

    if not unique_fields:
        if track_all:
            result["items"] = existing_data
        return result

    for field in unique_fields:
        result["used_identifiers"][field] = set()

    for item in existing_data:
        if not isinstance(item, dict):
            continue

        for field in unique_fields:
            if field in item:
                value = str(item[field]).lower().strip()
                result["used_identifiers"][field].add(value)

        if track_all:
            result["items"].append(item)

    if result["count"] > 0:
        logger.info(f"Loaded {result['count']} existing items")

    return result


def format_items_context(items: list[dict], primary_field: str, secondary_field: str | None = None, max_items: int = 40) -> str:
    """Format items for AI context to avoid duplicates."""
    if not items:
        return ""

    recent_items = items[-max_items:]
    formatted_items = []

    for item in recent_items:
        primary_value = item.get(primary_field, "")
        if not primary_value:
            continue

        if secondary_field and item.get(secondary_field):
            secondary_value = item[secondary_field]
            formatted_items.append(f"  - {primary_value} ({secondary_value})")
        else:
            formatted_items.append(f"  - {primary_value}")

    return "\n".join(formatted_items)


def validate_data_structure(data: list[dict], required_fields: list[str]) -> list[dict]:
    """Validate data structure and filter out invalid items."""
    valid_data = []
    invalid_count = 0

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.debug(f"Item {i} is not a dictionary, skipping")
            invalid_count += 1
            continue

        missing_fields = [field for field in required_fields if field not in item]
        if missing_fields:
            logger.debug(f"Item {i} missing required fields: {', '.join(missing_fields)}, skipping")
            invalid_count += 1
            continue

        valid_data.append(item)

    if invalid_count > 0:
        logger.warning(f"Filtered out {invalid_count} invalid items")

    return valid_data


def merge_data_with_existing(new_data: list[dict], existing_data: list[dict], unique_field: str = "id") -> tuple[list[dict], list[str]]:
    """Merge new data with existing data, avoiding duplicates."""
    existing_identifiers = set()
    for item in existing_data:
        if unique_field in item:
            identifier = str(item[unique_field]).lower().strip()
            existing_identifiers.add(identifier)

    merged_data = existing_data.copy()
    duplicates = []

    for item in new_data:
        if unique_field in item:
            identifier = str(item[unique_field]).lower().strip()
            if identifier in existing_identifiers:
                duplicates.append(identifier)
                logger.debug(f"Duplicate {unique_field} detected: {identifier}")
            else:
                existing_identifiers.add(identifier)
                merged_data.append(item)
        else:
            merged_data.append(item)

    if duplicates:
        logger.warning(f"Found {len(duplicates)} duplicates")

    return merged_data, duplicates


def check_and_filter_duplicates(items: list[dict], used_identifiers: dict[str, set], unique_fields: list[str], normalize_fn: dict[str, Callable] | None = None) -> dict:
    """
    Generic duplicate filtering across all generators.

    Args:
        items: List of items to check
        used_identifiers: Dict of field -> set of used values
        unique_fields: Fields to check for uniqueness
        normalize_fn: Optional dict of field -> normalization function

    Returns:
        {
            "unique_items": list,
            "duplicates_found": list,
            "updated_identifiers": dict
        }
    """
    unique_items = []
    duplicates = []
    new_identifiers = {k: v.copy() for k, v in used_identifiers.items()}

    for item in items:
        is_duplicate = False

        for field in unique_fields:
            value = item.get(field)
            if not value:
                continue

            # Apply normalization if provided, otherwise use default
            normalized_value = normalize_fn[field](value) if normalize_fn and field in normalize_fn else str(value).lower().strip()

            if normalized_value in new_identifiers.get(field, set()):
                duplicates.append(f"{field}:{normalized_value}")
                is_duplicate = True
                break

            new_identifiers.setdefault(field, set()).add(normalized_value)

        if not is_duplicate:
            unique_items.append(item)

    if duplicates:
        logger.debug(f"Filtered {len(duplicates)} duplicates")

    return {"unique_items": unique_items, "duplicates_found": duplicates, "updated_identifiers": new_identifiers}


def save_generated_data(items: list[dict], filepath: Path, item_type: str) -> None:
    """Save generated data with standard logging."""
    if items:
        save_to_json(items, filepath)
        logger.info(f"Saved {len(items)} {item_type} to {filepath}")


def load_with_duplicates(filepath: Path, unique_fields: list[str], track_all: bool = False) -> dict:
    """Load existing data with duplicate tracking - simplified wrapper."""
    existing = load_existing_data(filepath=filepath, unique_fields=unique_fields, track_all=track_all)

    return {
        "items": existing["items"] if track_all else [],
        "all_items": existing["items"].copy() if existing["items"] and track_all else [],
        "used_identifiers": existing["used_identifiers"],
    }
