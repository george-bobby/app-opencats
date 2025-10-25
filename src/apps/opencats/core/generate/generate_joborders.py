"""Generate job orders data for OpenCATS using AI."""

import asyncio
import random
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    COMPANIES_FILEPATH,
    CONTACTS_FILEPATH,
    DEFAULT_JOBORDERS_COUNT,
    JOB_TITLES,
    JOBORDERS_BATCH_SIZE,
    JOBORDERS_FILEPATH,
    TECH_SKILLS,
    OpenCATSJobType,
)
from apps.opencats.config.settings import settings
from apps.opencats.utils.data_utils import format_date_for_opencats, load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_joborders():
    """Load existing job orders to prevent duplicates."""
    existing_data = load_existing_data(JOBORDERS_FILEPATH)

    used_titles = set()

    for joborder in existing_data:
        if joborder.get("title"):
            used_titles.add(joborder["title"].lower())

    return {
        "used_titles": used_titles,
        "generated_joborders": existing_data,
    }


def load_companies_and_contacts():
    """Load companies and contacts for job order assignment."""
    companies_data = load_existing_data(COMPANIES_FILEPATH)
    contacts_data = load_existing_data(CONTACTS_FILEPATH)

    if not companies_data:
        logger.warning("No companies found. Job orders will be generated without company assignments.")
        return []

    # Create a mapping of companies with their contacts
    company_contacts = {}
    for idx, company in enumerate(companies_data):
        company_id = idx + 1  # Simulated company ID
        company_contacts[company_id] = {
            "company": {
                "id": company_id,
                "name": company.get("name", ""),
                "city": company.get("city", ""),
                "state": company.get("state", ""),
            },
            "contacts": [],
        }

    # Add contacts to their respective companies
    for contact in contacts_data:
        company_id = contact.get("companyID")
        if company_id and company_id in company_contacts:
            company_contacts[company_id]["contacts"].append(
                {
                    "id": len(company_contacts[company_id]["contacts"]) + 1,  # Simulated contact ID
                    "name": f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
                    "title": contact.get("title", ""),
                }
            )

    return list(company_contacts.values())


def create_joborders_prompt(used_titles: set, company_contacts: list[dict], batch_size: int) -> str:
    """Create prompt for job order generation."""
    excluded_titles_text = ""
    if used_titles:
        recent_titles = list(used_titles)[-10:]
        excluded_titles_text = f"\n\nDo not use these job titles (already exist): {', '.join(recent_titles)}"

    # Select random companies for this batch
    selected_companies = random.sample(company_contacts, min(batch_size, len(company_contacts))) if company_contacts else []

    companies_info = ""
    if selected_companies:
        companies_list = []
        for item in selected_companies:
            company = item["company"]
            contacts = item["contacts"]
            contact_info = ""
            if contacts:
                contact_names = [f"ID {c['id']}: {c['name']} ({c['title']})" for c in contacts[:3]]  # Show up to 3 contacts
                contact_info = f" - Contacts: {', '.join(contact_names)}"
            companies_list.append(f"Company ID {company['id']}: {company['name']} in {company['city']}, {company['state']}{contact_info}")
        companies_info = f"\n\nAssign job orders to these companies:\n{chr(10).join(companies_list)}"

    job_titles_list = ", ".join(random.sample(JOB_TITLES, min(15, len(JOB_TITLES))))
    skills_list = ", ".join(random.sample(TECH_SKILLS, min(20, len(TECH_SKILLS))))

    job_types = [jt.value for jt in OpenCATSJobType]
    job_types_info = f"Job types: {', '.join(job_types)} (C=Contract, C2H=Contract-to-Hire, FL=Freelance, H=Hire/Full-time)"

    prompt = f"""Generate {batch_size} realistic job orders for {settings.DATA_THEME_SUBJECT}.

Use these job titles: {job_titles_list}
Required skills: {skills_list}
{job_types_info}

Each job order should have:
- companyID: Company ID from the provided list (required)
- contactID: Contact ID from the company's contacts (optional, 80% chance)
- recruiter: Recruiter ID (use {settings.OPENCATS_RECRUITER_ID})
- owner: Owner ID (use {settings.OPENCATS_OWNER_ID})
- openings: Number of openings (1-5)
- title: Job title from the provided list
- companyJobID: Company's internal job ID (optional, 60% chance)
- type: Job type code (C, C2H, FL, or H)
- city: City name
- state: 2-letter US state code
- duration: Contract duration in months (only for Contract/C2H types, optional)
- department: Department name (optional, 70% chance)
- maxRate: Maximum hourly rate for contracts (optional, for C/C2H/FL types)
- salary: Annual salary for full-time positions (optional, for H type)
- description: Detailed job description (3-5 sentences)
- notes: Internal notes about the position (1-2 sentences, optional 60% chance)
- isHot: 1 for urgent positions (30% chance), 0 otherwise
- public: 1 for public job postings (70% chance), 0 otherwise
- startDate: Desired start date in MM-DD-YY format (optional, 50% chance)
- questionnaire: "none" (default)

Return as JSON array.{companies_info}{excluded_titles_text}"""

    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_joborders_batch(used_titles: set, company_contacts: list[dict], batch_size: int) -> list[dict[str, Any]]:
    """Generate a batch of job orders using AI."""
    try:
        prompt = create_joborders_prompt(used_titles, company_contacts, batch_size)

        # Explicitly access settings values to avoid attribute access issues in retry
        api_key = settings.ANTHROPIC_API_KEY
        model = settings.DEFAULT_MODEL

        response = await make_anthropic_request(
            prompt=prompt,
            api_key=api_key,
            model=model,
            max_tokens=4000,
            temperature=0.8,
        )

        if not response:
            logger.error("✖ Failed to get response from Anthropic API")
            return []

        joborders_data = parse_anthropic_response(response)
        if not joborders_data:
            logger.error("✖ Failed to parse job orders data from API response")
            return []

        # Validate and clean the data
        validated_joborders = []
        for joborder in joborders_data:
            if validate_joborder_data(joborder):
                # Clean and format the data
                cleaned_joborder = clean_joborder_data(joborder)
                validated_joborders.append(cleaned_joborder)
            else:
                logger.warning(f"⚠ Invalid job order data: {joborder}")

        return validated_joborders

    except Exception as e:
        logger.error(f"✖ Exception in generate_joborders_batch: {e}")
        logger.error(f"✖ Exception type: {type(e)}")
        raise


def validate_joborder_data(joborder: dict[str, Any]) -> bool:
    """Validate job order data structure."""
    required_fields = ["companyID", "recruiter", "owner", "openings", "title", "type", "city", "state"]

    for field in required_fields:
        if not joborder.get(field):
            return False

    # Validate job type
    valid_types = [jt.value for jt in OpenCATSJobType]
    return joborder.get("type") in valid_types


def clean_joborder_data(joborder: dict[str, Any]) -> dict[str, Any]:
    """Clean and format job order data."""
    # Handle contactID properly - convert to int or empty string
    contact_id = joborder.get("contactID", "")
    if contact_id:
        try:
            contact_id = int(contact_id)
        except (ValueError, TypeError):
            contact_id = ""
    else:
        contact_id = ""

    # Ensure all required fields exist with defaults
    cleaned = {
        "companyID": int(joborder.get("companyID", 1)),
        "contactID": contact_id,
        "recruiter": int(joborder.get("recruiter", settings.OPENCATS_RECRUITER_ID)),
        "owner": int(joborder.get("owner", settings.OPENCATS_OWNER_ID)),
        "openings": int(joborder.get("openings", 1)),
        "title": joborder.get("title", "").strip(),
        "companyJobID": joborder.get("companyJobID", "").strip(),
        "type": joborder.get("type", "H").strip().upper(),
        "city": joborder.get("city", "").strip(),
        "state": joborder.get("state", "").strip().upper(),
        "duration": str(joborder.get("duration", "")).strip(),
        "department": joborder.get("department", "").strip(),
        "maxRate": str(joborder.get("maxRate", "")).strip(),
        "salary": str(joborder.get("salary", "")).strip(),
        "description": joborder.get("description", "").strip(),
        "notes": joborder.get("notes", "").strip(),
        "isHot": 1 if joborder.get("isHot") else 0,
        "public": 1 if joborder.get("public") else 0,
        "startDate": format_date_for_opencats(joborder.get("startDate", "")),
        "questionnaire": joborder.get("questionnaire", "none").strip(),
    }

    return cleaned


async def joborders(n_joborders: int | None = None) -> dict[str, Any]:
    """Generate job orders data."""
    target_count = n_joborders or DEFAULT_JOBORDERS_COUNT
    logger.info(f"💼 Starting job order generation - Target: {target_count}")

    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    # Load existing data
    existing = load_existing_joborders()
    used_titles = existing["used_titles"]
    generated_joborders = existing["generated_joborders"]

    # Load companies and contacts for assignment
    company_contacts = load_companies_and_contacts()
    if not company_contacts:
        logger.error("❌ No companies available. Generate companies first.")
        return {"joborders": generated_joborders}

    current_count = len(generated_joborders)
    remaining_count = max(0, target_count - current_count)

    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} job orders, no generation needed")
        return {"joborders": generated_joborders}

    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")

    # Generate job orders in batches
    new_joborders = []
    batches = (remaining_count + JOBORDERS_BATCH_SIZE - 1) // JOBORDERS_BATCH_SIZE

    for batch_num in range(batches):
        batch_size = min(JOBORDERS_BATCH_SIZE, remaining_count - len(new_joborders))
        logger.info(f"🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} job orders)")

        try:
            batch_joborders = await generate_joborders_batch(used_titles, company_contacts, batch_size)

            if batch_joborders:
                # Update used titles to avoid duplicates
                for joborder in batch_joborders:
                    if joborder.get("title"):
                        used_titles.add(joborder["title"].lower())

                new_joborders.extend(batch_joborders)
                logger.info(f"✅ Generated {len(batch_joborders)} job orders in batch {batch_num + 1}")
            else:
                logger.warning(f"⚠️ No job orders generated in batch {batch_num + 1}")

        except Exception as e:
            logger.error(f"❌ Error in batch {batch_num + 1}: {e!s}")
            continue

        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)

    # Combine with existing data
    all_joborders = generated_joborders + new_joborders

    # Save to file
    if save_to_json(all_joborders, JOBORDERS_FILEPATH):
        logger.succeed(f"✅ Job order generation completed! Generated {len(new_joborders)} new job orders, total: {len(all_joborders)}")
    else:
        logger.error("❌ Failed to save job orders data")

    return {"joborders": all_joborders}
