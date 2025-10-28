"""Generate candidates data for OpenCATS using AI."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    CANDIDATES_BATCH_SIZE,
    CANDIDATES_FILEPATH,
    DEFAULT_CANDIDATES_COUNT,
    JOB_TITLES,
    TECH_SKILLS,
)
from apps.opencats.config.settings import settings
from apps.opencats.generate.prompts.generate_candidates_prompts import (
    EXCLUDED_EMAILS_TEMPLATE,
    EXCLUDED_NAMES_TEMPLATE,
    USER_PROMPT,
)
from apps.opencats.utils.data_utils import format_date_for_opencats, format_phone_number, load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_candidates():
    """Load existing candidates to prevent duplicates."""
    existing_data = load_existing_data(CANDIDATES_FILEPATH)

    used_emails = set()
    used_names = set()

    for candidate in existing_data:
        if candidate.get("email1"):
            used_emails.add(candidate["email1"].lower())
        if candidate.get("firstName") and candidate.get("lastName"):
            full_name = f"{candidate['firstName']} {candidate['lastName']}".lower()
            used_names.add(full_name)

    return {
        "used_emails": used_emails,
        "used_names": used_names,
        "generated_candidates": existing_data,
    }


def create_candidates_prompt(used_emails: set, used_names: set, batch_size: int) -> str:
    """Create prompt for candidate generation."""
    excluded_emails_text = ""
    if used_emails:
        recent_emails = list(used_emails)[-10:]
        excluded_emails_text = EXCLUDED_EMAILS_TEMPLATE.format(emails_list=", ".join(recent_emails))

    excluded_names_text = ""
    if used_names:
        recent_names = list(used_names)[-10:]
        excluded_names_text = EXCLUDED_NAMES_TEMPLATE.format(names_list=", ".join(recent_names))

    # Calculate percentages for variety
    experience_percentage = 80
    education_percentage = 70
    variety_factor = min(100, batch_size * 2)  # More variety for larger batches

    # Include realistic job market skills and titles for better data relationships
    import random

    relevant_skills = ", ".join(random.sample(TECH_SKILLS, min(15, len(TECH_SKILLS))))
    relevant_titles = ", ".join(random.sample(JOB_TITLES, min(10, len(JOB_TITLES))))

    prompt = USER_PROMPT.format(
        batch_size=batch_size,
        experience_percentage=experience_percentage,
        education_percentage=education_percentage,
        variety_factor=variety_factor,
        relevant_skills=relevant_skills,
        relevant_titles=relevant_titles,
        excluded_emails_text=excluded_emails_text,
        excluded_names_text=excluded_names_text,
    )

    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_candidates_batch(used_emails: set, used_names: set, batch_size: int) -> list[dict[str, Any]]:
    """Generate a batch of candidates using AI."""
    try:
        prompt = create_candidates_prompt(used_emails, used_names, batch_size)

        # Explicitly access settings values to avoid attribute access issues in retry
        api_key = settings.ANTHROPIC_API_KEY
        model = settings.DEFAULT_MODEL

        response = await make_anthropic_request(
            prompt=prompt,
            api_key=api_key,
            model=model,
            max_tokens=8000,
            temperature=0.8,
        )

        if not response:
            logger.error("✖ Failed to get response from Anthropic API")
            return []

        candidates_data = parse_anthropic_response(response)
        if not candidates_data:
            logger.error("✖ Failed to parse candidates data from API response")
            return []

        # Validate and clean the data
        validated_candidates = []
        for candidate in candidates_data:
            if validate_candidate_data(candidate):
                # Clean and format the data
                cleaned_candidate = clean_candidate_data(candidate)
                validated_candidates.append(cleaned_candidate)
            else:
                logger.warning(f"⚠ Invalid candidate data: {candidate}")

        return validated_candidates

    except Exception as e:
        logger.error(f"✖ Exception in generate_candidates_batch: {e}")
        logger.error(f"✖ Exception type: {type(e)}")
        raise


def validate_candidate_data(candidate: dict[str, Any]) -> bool:
    """Validate candidate data structure."""
    required_fields = ["firstName", "lastName"]

    return all(candidate.get(field) for field in required_fields)


def clean_candidate_data(candidate: dict[str, Any]) -> dict[str, Any]:
    """Clean and format candidate data."""
    # Ensure all required fields exist with defaults
    cleaned = {
        "firstName": candidate.get("firstName", "").strip() if candidate.get("firstName") else "",
        "middleName": candidate.get("middleName", "").strip() if candidate.get("middleName") else "",
        "lastName": candidate.get("lastName", "").strip() if candidate.get("lastName") else "",
        "email1": candidate.get("email1", "").strip().lower() if candidate.get("email1") else "",
        "email2": candidate.get("email2", "").strip().lower() if candidate.get("email2") else "",
        "phoneHome": format_phone_number(candidate.get("phoneHome", "")),
        "phoneCell": format_phone_number(candidate.get("phoneCell", "")),
        "phoneWork": format_phone_number(candidate.get("phoneWork", "")),
        "address": candidate.get("address", "").strip() if candidate.get("address") else "",
        "city": candidate.get("city", "").strip() if candidate.get("city") else "",
        "state": candidate.get("state", "").strip().upper() if candidate.get("state") else "",
        "zip": candidate.get("zip", "").strip() if candidate.get("zip") else "",
        "source": candidate.get("source", "").strip() if candidate.get("source") else "",
        "keySkills": candidate.get("keySkills", "").strip() if candidate.get("keySkills") else "",
        "dateAvailable": format_date_for_opencats(candidate.get("dateAvailable", "")),
        "currentEmployer": candidate.get("currentEmployer", "").strip() if candidate.get("currentEmployer") else "",
        "canRelocate": 1 if candidate.get("canRelocate") else 0,
        "currentPay": str(candidate.get("currentPay", "")).strip() if candidate.get("currentPay") else "",
        "desiredPay": str(candidate.get("desiredPay", "")).strip() if candidate.get("desiredPay") else "",
        "notes": candidate.get("notes", "").strip() if candidate.get("notes") else "",
        "webSite": candidate.get("webSite", "").strip() if candidate.get("webSite") else "",
        "bestTimeToCall": candidate.get("bestTimeToCall", "").strip() if candidate.get("bestTimeToCall") else "",
        "isHot": 1 if candidate.get("isHot") else 0,
        "gender": candidate.get("gender", "").strip().upper() if candidate.get("gender") else "",
        "race": validate_eeo_ethnic_type(candidate.get("race")),
        "veteran": validate_eeo_veteran_type(candidate.get("veteran")),
        "disability": candidate.get("disability", "").strip().upper() if candidate.get("disability") else "",
        "textResumeBlock": candidate.get("textResumeBlock", "").strip() if candidate.get("textResumeBlock") else "",
        "textResumeFilename": candidate.get("textResumeFilename", "").strip() if candidate.get("textResumeFilename") else "",
        "associatedAttachment": "",  # Not used in generation
    }

    return cleaned


def validate_eeo_ethnic_type(value: Any) -> int:
    """Validate EEO ethnic type value."""
    if not value:
        return 0

    try:
        int_value = int(value)
        if 1 <= int_value <= 5:
            return int_value
    except (ValueError, TypeError):
        pass

    return 0


def validate_eeo_veteran_type(value: Any) -> int:
    """Validate EEO veteran type value."""
    if not value:
        return 0

    try:
        int_value = int(value)
        if 1 <= int_value <= 4:
            return int_value
    except (ValueError, TypeError):
        pass

    return 0


async def candidates(n_candidates: int | None = None) -> dict[str, Any]:
    """Generate candidates data."""
    target_count = n_candidates or DEFAULT_CANDIDATES_COUNT
    logger.info(f"👨‍💼 Starting candidate generation - Target: {target_count}")

    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    # Load existing data
    existing = load_existing_candidates()
    used_emails = existing["used_emails"]
    used_names = existing["used_names"]
    generated_candidates = existing["generated_candidates"]

    current_count = len(generated_candidates)
    remaining_count = max(0, target_count - current_count)

    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} candidates, no generation needed")
        return {"candidates": generated_candidates}

    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")

    # Generate candidates in batches
    new_candidates = []
    batches = (remaining_count + CANDIDATES_BATCH_SIZE - 1) // CANDIDATES_BATCH_SIZE
    consecutive_failures = 0
    max_consecutive_failures = 3

    for batch_num in range(batches):
        batch_size = min(CANDIDATES_BATCH_SIZE, remaining_count - len(new_candidates))
        logger.info(f"ℹ 🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} candidates)")

        try:
            batch_candidates = await generate_candidates_batch(used_emails, used_names, batch_size)

            if batch_candidates:
                # Reset failure counter on successful batch
                consecutive_failures = 0

                # Update used identifiers to avoid duplicates
                for candidate in batch_candidates:
                    if candidate.get("email1"):
                        used_emails.add(candidate["email1"].lower())
                    if candidate.get("firstName") and candidate.get("lastName"):
                        full_name = f"{candidate['firstName']} {candidate['lastName']}".lower()
                        used_names.add(full_name)

                new_candidates.extend(batch_candidates)
                logger.info(f"✔ ✅ Generated {len(batch_candidates)} candidates in batch {batch_num + 1}")
            else:
                consecutive_failures += 1
                logger.warning(f"⚠ ⚠️ No candidates generated in batch {batch_num + 1}")

                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"✖ Too many consecutive failures ({consecutive_failures}). Stopping generation.")
                    break

        except Exception as e:
            consecutive_failures += 1
            logger.error(f"✖ Error in batch {batch_num + 1}: {e!s}")

            if consecutive_failures >= max_consecutive_failures:
                logger.error(f"✖ Too many consecutive failures ({consecutive_failures}). Stopping generation.")
                break
            continue

        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)

    # Combine with existing data
    all_candidates = generated_candidates + new_candidates

    # Save to file
    if save_to_json(all_candidates, CANDIDATES_FILEPATH):
        logger.succeed(f"✔ ✅ Candidate generation completed! Generated {len(new_candidates)} new candidates, total: {len(all_candidates)}")
    else:
        logger.error("✖ Failed to save candidates data")

    return {"candidates": all_candidates}
