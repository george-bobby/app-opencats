"""Seed candidate_joborder junction table to connect candidates with job orders."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.constants import CANDIDATES_FILEPATH, JOBORDERS_FILEPATH
from apps.opencats.utils.api_utils import OpenCATSAPIUtils
from apps.opencats.utils.data_utils import load_existing_data
from common.logger import logger


# Pipeline status definitions from OpenCATS
PIPELINE_STATUSES = [
    (100, "No Contact"),
    (200, "Contacted"),
    (300, "Submitted"),
    (400, "Applied"),
    (500, "Interviewing"),
    (600, "Offer Extended"),
    (700, "Offer Accepted"),
    (800, "Offer Declined"),
    (900, "Placed"),
    (1000, "Rejected"),
]


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def seed_candidate_joborder() -> dict[str, Any]:
    """Seed candidate_joborder junction table with realistic associations.

    This creates many-to-many relationships between candidates and job orders.
    Each job order will have 1-8 candidates in different stages of the hiring pipeline.
    """
    logger.info("🔗 Starting candidate-job order associations seeding...")

    # Load candidates and job orders data to get the mapping
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

    associations_created = 0
    error_count = 0
    associations = []
    used_combinations = set()  # Prevent duplicate candidate-job associations

    async with OpenCATSAPIUtils() as api:
        # Get all seeded candidates and job orders from OpenCATS to get their actual IDs
        logger.info("📊 Fetching seeded candidates from OpenCATS...")
        seeded_candidates = await api.get_all_items("candidates")
        
        logger.info("📊 Fetching seeded job orders from OpenCATS...")
        seeded_joborders = await api.get_all_items("joborders")

        if not seeded_candidates or not seeded_joborders:
            logger.error("❌ Could not retrieve candidates or job orders from OpenCATS")
            return {"associations_created": 0, "errors": 1}

        logger.info(f"✅ Retrieved {len(seeded_candidates)} candidates and {len(seeded_joborders)} job orders")

        # Create associations for each job order
        for job_idx, joborder_data in enumerate(seeded_joborders):
            # Randomly select 1-8 candidates for this job order
            num_candidates = random.randint(1, min(8, len(seeded_candidates)))
            available_candidates = [c for c in seeded_candidates]
            random.shuffle(available_candidates)
            selected_candidates = available_candidates[:num_candidates]

            joborder_id = joborder_data.get("jobOrderID")
            joborder_title = joborder_data.get("title", "Unknown")

            if not joborder_id:
                logger.warning(f"⚠️ Skipping job order without ID: {joborder_title}")
                continue

            logger.info(f"🔄 Creating associations for job '{joborder_title}' (ID: {joborder_id}) with {num_candidates} candidates")

            for candidate_data in selected_candidates:
                candidate_id = candidate_data.get("candidateID")
                candidate_name = f"{candidate_data.get('firstName', '')} {candidate_data.get('lastName', '')}".strip()

                if not candidate_id:
                    logger.warning(f"⚠️ Skipping candidate without ID: {candidate_name}")
                    continue

                # Create unique key to avoid duplicates
                combo_key = (candidate_id, joborder_id)
                if combo_key in used_combinations:
                    continue
                used_combinations.add(combo_key)

                # Assign realistic status from weighted pool
                status_id, status_name = random.choice(status_pool)

                # Generate a realistic date_submitted (within last 90 days)
                days_ago = random.randint(1, 90)
                date_submitted = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

                try:
                    # Create association using the correct GET endpoint
                    # Based on nginx log: GET /index.php?m=joborders&a=addToPipeline&getback=getback&jobOrderID=17&candidateID=15
                    association_url = f"/index.php?m=joborders&a=addToPipeline&getback=getback&jobOrderID={joborder_id}&candidateID={candidate_id}"
                    
                    # Make GET request to add candidate to pipeline
                    result = await api.get_request(association_url)

                    if result and result.get("status_code") == 200:
                        logger.info(f"✅ Associated candidate '{candidate_name}' (ID: {candidate_id}) with job '{joborder_title}' (ID: {joborder_id}) - Status: {status_name} ({status_id})")
                        
                        # Now update the status if it's not the default
                        if status_id != 100:  # If not "No Contact" status
                            # Update the pipeline status using AJAX or form submission
                            await api.update_pipeline_status(candidate_id, joborder_id, status_id)
                        
                        associations.append(
                            {
                                "candidate_id": candidate_id,
                                "candidate_name": candidate_name,
                                "joborder_id": joborder_id,
                                "job_order": joborder_title,
                                "status_id": status_id,
                                "status_name": status_name,
                                "date_submitted": date_submitted,
                            }
                        )
                        associations_created += 1
                    else:
                        logger.warning(f"⚠️ Failed to associate candidate '{candidate_name}' with job '{joborder_title}': {result}")
                        error_count += 1

                except Exception as e:
                    logger.error(f"❌ Error creating association for candidate '{candidate_name}' and job '{joborder_title}': {e!s}")
                    error_count += 1

                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.3)

            # Delay between job orders
            await asyncio.sleep(0.5)

    logger.succeed(f"✅ Candidate-job order associations seeding completed! Created: {associations_created}, Errors: {error_count}")

    # Log status distribution summary
    if associations:
        status_summary = {}
        for assoc in associations:
            status_name = assoc["status_name"]
            status_summary[status_name] = status_summary.get(status_name, 0) + 1

        logger.info(f"📊 Status distribution: {status_summary}")

    return {
        "associations_created": associations_created,
        "errors": error_count,
        "details": associations,
        "status_summary": status_summary if associations else {},
    }

