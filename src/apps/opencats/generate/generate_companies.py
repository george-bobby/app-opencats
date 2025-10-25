"""Generate companies data for OpenCATS using AI."""

import asyncio
import random
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.opencats.config.constants import (
    COMPANIES_BATCH_SIZE,
    COMPANIES_FILEPATH,
    COMPANY_INDUSTRIES,
    COMPANY_TECHNOLOGIES,
    DEFAULT_COMPANIES_COUNT,
    MAJOR_CITIES,
)
from apps.opencats.config.settings import settings
from apps.opencats.utils.data_utils import load_existing_data
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_companies():
    """Load existing companies to prevent duplicates."""
    existing_data = load_existing_data(COMPANIES_FILEPATH)

    used_names = set()
    used_urls = set()

    for company in existing_data:
        if company.get("name"):
            used_names.add(company["name"].lower())
        if company.get("url"):
            used_urls.add(company["url"].lower())

    return {
        "used_names": used_names,
        "used_urls": used_urls,
        "generated_companies": existing_data,
    }


def create_companies_prompt(used_names: set, batch_size: int) -> str:
    """Create prompt for company generation."""
    excluded_names_text = ""
    if used_names:
        recent_names = list(used_names)[-10:]
        excluded_names_text = f"\n\nDo not use these company names (already exist): {', '.join(recent_names)}"

    industries_list = ", ".join(random.sample(COMPANY_INDUSTRIES, min(8, len(COMPANY_INDUSTRIES))))
    technologies_list = ", ".join(random.sample(COMPANY_TECHNOLOGIES, min(10, len(COMPANY_TECHNOLOGIES))))
    cities_list = ", ".join(random.sample(MAJOR_CITIES, min(15, len(MAJOR_CITIES))))

    prompt = f"""Generate {batch_size} realistic companies for {settings.DATA_THEME_SUBJECT}. 

Create diverse companies across these industries: {industries_list}
Use these technologies: {technologies_list}
Use these cities: {cities_list}

Each company should have:
- name: Realistic company name (avoid generic names like "Tech Corp")
- address: Street address
- city: City name from the provided list
- state: 2-letter US state code
- zip: 5-digit ZIP code
- phone1: Primary phone number in format (XXX) XXX-XXXX
- phone2: Secondary phone (optional, 30% chance)
- faxNumber: Fax number (optional, 20% chance)
- url: Company website URL (https://companyname.com format)
- keyTechnologies: 2-4 relevant technologies from the list, comma-separated
- notes: Brief description of what the company does (1-2 sentences)
- isHot: 1 for high-priority companies (20% chance), 0 otherwise
- departmentsCSV: 2-4 relevant departments, comma-separated (e.g., "Engineering,Sales,Marketing")

Return as JSON array.{excluded_names_text}"""

    return prompt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_companies_batch(used_names: set, batch_size: int) -> list[dict[str, Any]]:
    """Generate a batch of companies using AI."""
    prompt = create_companies_prompt(used_names, batch_size)

    response = await make_anthropic_request(
        prompt=prompt,
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.DEFAULT_MODEL,
        max_tokens=4000,
        temperature=0.8,
    )

    if not response:
        logger.error("Failed to get response from Anthropic API")
        return []

    companies_data = parse_anthropic_response(response)
    if not companies_data:
        logger.error("Failed to parse companies data from API response")
        return []

    # Validate and clean the data
    validated_companies = []
    for company in companies_data:
        if validate_company_data(company):
            # Clean and format the data
            cleaned_company = clean_company_data(company)
            validated_companies.append(cleaned_company)
        else:
            logger.warning(f"Invalid company data: {company}")

    return validated_companies


def validate_company_data(company: dict[str, Any]) -> bool:
    """Validate company data structure."""
    required_fields = ["name", "city", "state"]

    return all(company.get(field) for field in required_fields)


def clean_company_data(company: dict[str, Any]) -> dict[str, Any]:
    """Clean and format company data."""
    # Ensure all required fields exist with defaults
    cleaned = {
        "name": company.get("name", "").strip(),
        "address": company.get("address", "").strip(),
        "city": company.get("city", "").strip(),
        "state": company.get("state", "").strip().upper(),
        "zip": company.get("zip", "").strip(),
        "phone1": format_phone(company.get("phone1", "")),
        "phone2": format_phone(company.get("phone2", "")),
        "faxNumber": format_phone(company.get("faxNumber", "")),
        "url": format_url(company.get("url", "")),
        "keyTechnologies": company.get("keyTechnologies", "").strip(),
        "notes": company.get("notes", "").strip(),
        "isHot": 1 if company.get("isHot") else 0,
        "departmentsCSV": company.get("departmentsCSV", "").strip(),
    }

    return cleaned


def format_phone(phone: str) -> str:
    """Format phone number."""
    if not phone:
        return ""

    # Extract digits
    digits = "".join(filter(str.isdigit, phone))

    # Format as (XXX) XXX-XXXX if 10 digits
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

    return phone


def format_url(url: str) -> str:
    """Format URL."""
    if not url:
        return ""

    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    return url


async def companies(n_companies: int | None = None) -> dict[str, Any]:
    """Generate companies data."""
    target_count = n_companies or DEFAULT_COMPANIES_COUNT
    logger.info(f"🏢 Starting company generation - Target: {target_count}")

    # Ensure data directory exists
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)

    # Validate API configuration
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    # Load existing data
    existing = load_existing_companies()
    used_names = existing["used_names"]
    generated_companies = existing["generated_companies"]

    current_count = len(generated_companies)
    remaining_count = max(0, target_count - current_count)

    if remaining_count == 0:
        logger.info(f"✅ Already have {current_count} companies, no generation needed")
        return {"companies": generated_companies}

    logger.info(f"📊 Current: {current_count}, Target: {target_count}, Generating: {remaining_count}")

    # Generate companies in batches
    new_companies = []
    batches = (remaining_count + COMPANIES_BATCH_SIZE - 1) // COMPANIES_BATCH_SIZE

    for batch_num in range(batches):
        batch_size = min(COMPANIES_BATCH_SIZE, remaining_count - len(new_companies))
        logger.info(f"🔄 Generating batch {batch_num + 1}/{batches} ({batch_size} companies)")

        try:
            batch_companies = await generate_companies_batch(used_names, batch_size)

            if batch_companies:
                # Update used names to avoid duplicates
                for company in batch_companies:
                    used_names.add(company["name"].lower())

                new_companies.extend(batch_companies)
                logger.info(f"✅ Generated {len(batch_companies)} companies in batch {batch_num + 1}")
            else:
                logger.warning(f"⚠️ No companies generated in batch {batch_num + 1}")

        except Exception as e:
            logger.error(f"❌ Error in batch {batch_num + 1}: {e!s}")
            continue

        # Small delay between batches
        if batch_num < batches - 1:
            await asyncio.sleep(1)

    # Combine with existing data
    all_companies = generated_companies + new_companies

    # Save to file
    if save_to_json(all_companies, COMPANIES_FILEPATH):
        logger.succeed(f"✅ Company generation completed! Generated {len(new_companies)} new companies, total: {len(all_companies)}")
    else:
        logger.error("❌ Failed to save companies data")

    return {"companies": all_companies}
