"""Data utilities for OpenCATS - JSON file operations and data validation."""

import json
from pathlib import Path
from typing import Any

from common.logger import logger


def load_json_file(filepath: Path) -> list[dict[str, Any]]:
    """Load data from a JSON file."""
    try:
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
                else:
                    logger.warning(f"Unexpected data format in {filepath}")
                    return []
        else:
            logger.info(f"File {filepath} does not exist, returning empty list")
            return []
    except Exception as e:
        logger.error(f"Error loading JSON file {filepath}: {e!s}")
        return []


def save_json_file(filepath: Path, data: list[dict[str, Any]]) -> bool:
    """Save data to a JSON file."""
    try:
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Saved {len(data)} records to {filepath}")
        return True

    except Exception as e:
        logger.error(f"❌ Error saving JSON file {filepath}: {e!s}")
        return False


def load_existing_data(filepath: Path) -> list[dict[str, Any]]:
    """Load existing data from file, return empty list if file doesn't exist."""
    return load_json_file(filepath)


def validate_data_structure(data: list[dict[str, Any]], required_fields: list[str]) -> bool:
    """Validate that data contains required fields."""
    if not data:
        return True  # Empty data is valid

    for item in data:
        if not isinstance(item, dict):
            logger.error("Data item is not a dictionary")
            return False

        for field in required_fields:
            if field not in item:
                logger.error(f"Required field '{field}' missing from data item")
                return False

    return True


def merge_data(existing_data: list[dict[str, Any]], new_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge new data with existing data, avoiding duplicates based on key fields."""
    if not existing_data:
        return new_data

    if not new_data:
        return existing_data

    # For now, just append new data
    # In a more sophisticated implementation, we could check for duplicates
    return existing_data + new_data


def format_phone_number(phone: str) -> str:
    """Format phone number for OpenCATS."""
    if not phone:
        return ""

    # Remove all non-digit characters
    digits = "".join(filter(str.isdigit, phone))

    # Format as (XXX) XXX-XXXX if 10 digits
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        # Remove leading 1 and format
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        # Return as-is if not standard format
        return phone


def format_date_for_opencats(date_str: str) -> str:
    """Format date string for OpenCATS (MM-DD-YY format)."""
    if not date_str:
        return ""

    try:
        # If date is in YYYY-MM-DD format, convert to MM-DD-YY
        if len(date_str) == 10 and date_str.count("-") == 2:
            year, month, day = date_str.split("-")
            return f"{month}-{day}-{year[2:]}"
        else:
            return date_str
    except Exception:
        return date_str


def clean_text_for_form(text: str) -> str:
    """Clean text for form submission."""
    if not text:
        return ""

    # Remove or replace problematic characters
    text = text.replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())  # Normalize whitespace

    return text


def extract_skills_from_text(text: str, skill_list: list[str]) -> list[str]:
    """Extract skills from text based on a predefined skill list."""
    if not text:
        return []

    text_lower = text.lower()
    found_skills = []

    for skill in skill_list:
        if skill.lower() in text_lower:
            found_skills.append(skill)

    return found_skills


def generate_email_from_name(first_name: str, last_name: str, domain: str = "example.com") -> str:
    """Generate an email address from first and last name."""
    if not first_name or not last_name:
        return f"user@{domain}"

    # Clean names and create email
    first_clean = "".join(c.lower() for c in first_name if c.isalnum())
    last_clean = "".join(c.lower() for c in last_name if c.isalnum())

    return f"{first_clean}.{last_clean}@{domain}"


def get_random_choice(choices: list[Any]) -> Any:
    """Get a random choice from a list."""
    import random

    return random.choice(choices) if choices else None


def get_random_choices(choices: list[Any], count: int) -> list[Any]:
    """Get multiple random choices from a list."""
    import random

    if not choices or count <= 0:
        return []

    return random.choices(choices, k=min(count, len(choices)))
