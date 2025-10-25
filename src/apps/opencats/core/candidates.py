"""Seed candidates data into OpenCATS."""

import asyncio
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import CANDIDATES_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def seed_candidates() -> dict[str, Any]:
    """Seed candidates data into OpenCATS."""
    logger.info("👨‍💼 Starting candidate seeding...")

    # Load generated candidates data
    candidates_data = load_existing_data(CANDIDATES_FILEPATH)

    if not candidates_data:
        logger.warning("⚠️ No candidates data found. Run generation first.")
        return {"seeded_candidates": 0, "errors": 0}

    logger.info(f"📊 Found {len(candidates_data)} candidates to seed")

    seeded_count = 0
    error_count = 0
    seeded_candidates = []

    async with OpenCATSAPIUtils() as api:
        for idx, candidate in enumerate(candidates_data):
            candidate_name = f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip()
            logger.info(f"🔄 Seeding candidate {idx + 1}/{len(candidates_data)}: {candidate_name}")

            try:
                # Prepare form data for OpenCATS
                form_data = prepare_candidate_form_data(candidate)

                # Submit to OpenCATS
                result = await api.submit_form(OpenCATSEndpoint.CANDIDATES_ADD.value, form_data)

                if result and result.get("status_code") == 200:
                    entity_id = result.get("entity_id")
                    if entity_id:
                        logger.info(f"✅ Candidate '{candidate_name}' seeded successfully (ID: {entity_id})")
                        seeded_candidates.append({"original_data": candidate, "opencats_id": entity_id, "status": "success"})
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ Candidate '{candidate_name}' may have been created but ID not found")
                        seeded_candidates.append({"original_data": candidate, "opencats_id": None, "status": "unknown"})
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed candidate '{candidate_name}': {result}")
                    seeded_candidates.append({"original_data": candidate, "opencats_id": None, "status": "failed", "error": str(result)})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error seeding candidate '{candidate_name}': {e!s}")
                seeded_candidates.append({"original_data": candidate, "opencats_id": None, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Candidate seeding completed! Seeded: {seeded_count}, Errors: {error_count}")

    return {"seeded_candidates": seeded_count, "errors": error_count, "details": seeded_candidates}


def prepare_candidate_form_data(candidate: dict[str, Any]) -> dict[str, str]:
    """Prepare candidate data for OpenCATS form submission."""
    form_data = {
        "postback": "postback",
        "firstName": candidate.get("firstName", ""),
        "middleName": candidate.get("middleName", ""),
        "lastName": candidate.get("lastName", ""),
        "email1": candidate.get("email1", ""),
        "email2": candidate.get("email2", ""),
        "phoneHome": candidate.get("phoneHome", ""),
        "phoneCell": candidate.get("phoneCell", ""),
        "phoneWork": candidate.get("phoneWork", ""),
        "address": candidate.get("address", ""),
        "city": candidate.get("city", ""),
        "state": candidate.get("state", ""),
        "zip": candidate.get("zip", ""),
        "source": candidate.get("source", ""),
        "keySkills": candidate.get("keySkills", ""),
        "dateAvailable": candidate.get("dateAvailable", ""),
        "currentEmployer": candidate.get("currentEmployer", ""),
        "currentPay": candidate.get("currentPay", ""),
        "desiredPay": candidate.get("desiredPay", ""),
        "notes": candidate.get("notes", ""),
        "webSite": candidate.get("webSite", ""),
        "bestTimeToCall": candidate.get("bestTimeToCall", ""),
        "gender": candidate.get("gender", ""),
        "disability": candidate.get("disability", ""),
        "textResumeBlock": candidate.get("textResumeBlock", ""),
        "textResumeFilename": candidate.get("textResumeFilename", ""),
        "associatedAttachment": candidate.get("associatedAttachment", ""),
    }

    # Handle checkboxes and numeric fields
    if candidate.get("canRelocate"):
        form_data["canRelocate"] = "1"

    # Handle EEO fields (only include if they have valid values)
    if candidate.get("race") and candidate.get("race") != 0:
        form_data["race"] = str(candidate.get("race"))

    if candidate.get("veteran") and candidate.get("veteran") != 0:
        form_data["veteran"] = str(candidate.get("veteran"))

    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}

    return form_data
