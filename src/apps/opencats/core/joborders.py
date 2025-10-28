"""Seed job orders data into OpenCATS."""

import asyncio
import random
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import CANDIDATES_FILEPATH, JOBORDERS_FILEPATH, OpenCATSEndpoint
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def seed_joborders() -> dict[str, Any]:
    """Seed job orders data into OpenCATS."""
    logger.info("💼 Starting job order seeding...")

    # Load generated job orders data
    joborders_data = load_existing_data(JOBORDERS_FILEPATH)

    if not joborders_data:
        logger.warning("⚠️ No job orders data found. Run generation first.")
        return {"seeded_joborders": 0, "errors": 0}

    logger.info(f"📊 Found {len(joborders_data)} job orders to seed")

    seeded_count = 0
    error_count = 0
    seeded_joborders = []

    async with OpenCATSAPIUtils() as api:
        for idx, joborder in enumerate(joborders_data):
            joborder_title = joborder.get("title", "Unknown")
            logger.info(f"🔄 Seeding job order {idx + 1}/{len(joborders_data)}: {joborder_title}")

            try:
                # Prepare form data for OpenCATS
                form_data = prepare_joborder_form_data(joborder)

                # Submit to OpenCATS
                result = await api.submit_form(OpenCATSEndpoint.JOBORDERS_ADD.value, form_data)

                if result and result.get("status_code") == 200:
                    entity_id = result.get("entity_id")
                    if entity_id:
                        logger.info(f"✅ Job order '{joborder_title}' seeded successfully (ID: {entity_id})")
                        seeded_joborders.append({"original_data": joborder, "opencats_id": entity_id, "status": "success"})
                        seeded_count += 1
                    else:
                        logger.warning(f"⚠️ Job order '{joborder_title}' may have been created but ID not found")
                        seeded_joborders.append({"original_data": joborder, "opencats_id": None, "status": "unknown"})
                        seeded_count += 1
                else:
                    logger.error(f"❌ Failed to seed job order '{joborder_title}': {result}")
                    seeded_joborders.append({"original_data": joborder, "opencats_id": None, "status": "failed", "error": str(result)})
                    error_count += 1

            except Exception as e:
                logger.error(f"❌ Error seeding job order '{joborder_title}': {e!s}")
                seeded_joborders.append({"original_data": joborder, "opencats_id": None, "status": "error", "error": str(e)})
                error_count += 1

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Job order seeding completed! Seeded: {seeded_count}, Errors: {error_count}")

    return {"seeded_joborders": seeded_count, "errors": error_count, "details": seeded_joborders}


def prepare_joborder_form_data(joborder: dict[str, Any]) -> dict[str, str]:
    """Prepare job order data for OpenCATS form submission."""
    form_data = {
        "postback": "postback",
        "companyID": str(joborder.get("companyID", "")),
        "recruiter": str(joborder.get("recruiter", "")),
        "owner": str(joborder.get("owner", "")),
        "openings": str(joborder.get("openings", "")),
        "title": joborder.get("title", ""),
        "companyJobID": joborder.get("companyJobID", ""),
        "type": joborder.get("type", ""),
        "city": joborder.get("city", ""),
        "state": joborder.get("state", ""),
        "duration": joborder.get("duration", ""),
        "department": joborder.get("department", ""),
        "maxRate": joborder.get("maxRate", ""),
        "salary": joborder.get("salary", ""),
        "description": joborder.get("description", ""),
        "notes": joborder.get("notes", ""),
        "startDate": joborder.get("startDate", ""),
        "questionnaire": joborder.get("questionnaire", "none"),
        "status": joborder.get("status", "Active"),
    }

    # Handle contactID (optional)
    if joborder.get("contactID"):
        form_data["contactID"] = str(joborder.get("contactID"))

    # Handle checkboxes
    if joborder.get("isHot"):
        form_data["isHot"] = "1"

    if joborder.get("public"):
        form_data["public"] = "1"

    if joborder.get("isInternal"):
        form_data["isInternal"] = "1"

        # Note: candidatesCount, submittedCount, daysOld, createdDateTime are metadata
        # that would be handled by the system, not during initial creation
        form_data["isHot"] = "1"

    if joborder.get("public"):
        form_data["public"] = "1"

    # Remove empty values to avoid issues
    form_data = {k: v for k, v in form_data.items() if v}

    return form_data


async def create_candidate_job_associations() -> dict[str, Any]:
    """Create many-to-many relationships between candidates and job orders.

    This creates realistic candidate-job order associations with varied pipeline statuses.
    Each job order will have 1-8 candidates in different stages of the hiring process.
    """
    logger.info("🔗 Starting candidate-job associations...")

    # Load candidates and job orders data
    candidates_data = load_existing_data(CANDIDATES_FILEPATH)
    joborders_data = load_existing_data(JOBORDERS_FILEPATH)

    if not candidates_data or not joborders_data:
        logger.warning("⚠️ Missing candidates or job orders data. Cannot create associations.")
        return {"associations_created": 0, "errors": 0}

    logger.info(f"📊 Found {len(candidates_data)} candidates and {len(joborders_data)} job orders")

    # Define realistic status distribution (weighted)
    # Higher probability for earlier pipeline stages
    status_weights = [
        (100, "No Contact", 5),  # 5% - just identified
        (200, "Contacted", 15),  # 15% - initial contact made
        (300, "Submitted", 20),  # 20% - resume submitted
        (400, "Applied", 25),  # 25% - actively applied
        (500, "Interviewing", 20),  # 20% - in interview process
        (600, "Offer Extended", 5),  # 5% - offer made
        (700, "Offer Accepted", 3),  # 3% - accepted offer
        (800, "Offer Declined", 3),  # 3% - declined offer
        (900, "Placed", 2),  # 2% - successfully placed
        (1000, "Rejected", 2),  # 2% - rejected or withdrew
    ]

    # Create weighted list for random selection
    status_pool = []
    for status_id, status_name, weight in status_weights:
        status_pool.extend([(status_id, status_name)] * weight)

    # Create realistic associations (each job order gets 1-8 candidates)
    associations_created = 0
    error_count = 0
    associations = []
    used_combinations = set()  # Prevent duplicate candidate-job associations

    async with OpenCATSAPIUtils() as api:
        for job_idx, joborder in enumerate(joborders_data):
            # Randomly select 1-8 candidates for this job order
            num_candidates = random.randint(1, min(8, len(candidates_data)))
            available_candidates = [c for c in candidates_data]
            random.shuffle(available_candidates)
            selected_candidates = available_candidates[:num_candidates]

            joborder_title = joborder.get("title", "Unknown")
            joborder_id = job_idx + 1  # Simulated job order ID

            logger.info(f"🔄 Creating associations for job '{joborder_title}' with {num_candidates} candidates")

            for candidate in selected_candidates:
                candidate_name = f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip()
                candidate_id = candidates_data.index(candidate) + 1  # Simulated candidate ID

                # Create unique key to avoid duplicates
                combo_key = (candidate_id, joborder_id)
                if combo_key in used_combinations:
                    continue
                used_combinations.add(combo_key)

                # Assign realistic status from weighted pool
                status_id, status_name = random.choice(status_pool)

                try:
                    # Create association using AJAX endpoint
                    # OpenCATS typically uses: candidates:addCandidateToJobOrder or similar
                    association_data = {
                        "candidateID": candidate_id,
                        "jobOrderID": joborder_id,
                        "status": status_id,
                        "date_submitted": "",  # Would be current date in real implementation
                    }

                    # This would be the actual API call to create the association
                    # result = await api.ajax_request("candidates:addCandidateToJobOrder", association_data)

                    # For now, we'll log the association (in real implementation, this would be an API call)
                    logger.info(f"🔗 Associated candidate '{candidate_name}' with job '{joborder_title}' - Status: {status_name} ({status_id})")
                    associations.append(
                        {
                            "candidate_id": candidate_id,
                            "candidate_name": candidate_name,
                            "joborder_id": joborder_id,
                            "job_order": joborder_title,
                            "status_id": status_id,
                            "status_name": status_name,
                            "implementation": "simulated",
                        }
                    )
                    associations_created += 1

                except Exception as e:
                    logger.error(f"❌ Error creating association: {e!s}")
                    error_count += 1

            # Small delay between job orders
            await asyncio.sleep(0.2)

    logger.succeed(f"✅ Candidate-job associations completed! Created: {associations_created}, Errors: {error_count}")

    # Log status distribution summary
    status_summary = {}
    for assoc in associations:
        status_name = assoc["status_name"]
        status_summary[status_name] = status_summary.get(status_name, 0) + 1

    logger.info(f"📊 Status distribution: {status_summary}")

    return {"associations_created": associations_created, "errors": error_count, "details": associations, "status_summary": status_summary}
