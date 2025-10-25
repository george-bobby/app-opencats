import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import (
    CUSTOMERS_BATCH_SIZE,
    CUSTOMERS_FILEPATH,
    DEFAULT_CUSTOMERS_COUNT,
    INCLUDE_COMPANY_RATIO,
    INCLUDE_PERSONAL_INFO_RATIO,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_customers_prompts import (
    EXCLUDED_EMAILS_TEMPLATE,
    USER_PROMPT,
)
from apps.medusa.utils.data_utils import load_existing_data, validate_data_structure
from common.anthropic_client import make_anthropic_request, parse_anthropic_response, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_customers():
    """Load existing customers to prevent duplicates."""
    existing = load_existing_data(filepath=CUSTOMERS_FILEPATH, unique_fields=["email", "phone", "first_name", "company_name"], track_all=False)

    return {
        "used_emails": existing["used_identifiers"].get("email", set()),
        "used_phones": existing["used_identifiers"].get("phone", set()),
        "used_names": existing["used_identifiers"].get("first_name", set()),
        "used_companies": existing["used_identifiers"].get("company_name", set()),
        "generated_customers": existing["items"],
    }


def normalize_phone(phone: str) -> str:
    """Normalize phone number to last 10 digits."""
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, phone))
    return digits[-10:] if len(digits) >= 10 else digits


def create_customers_prompt(used_emails: set[str], batch_size: int) -> str:
    """Create prompt for customer generation."""
    excluded_emails_text = ""
    if used_emails:
        recent_emails = list(used_emails)[-10:]
        excluded_emails_text = EXCLUDED_EMAILS_TEMPLATE.format(emails_list=", ".join(recent_emails))

    variety_factor = 150
    return USER_PROMPT.format(
        batch_size=batch_size,
        personal_info_percentage=int(INCLUDE_PERSONAL_INFO_RATIO * 100),
        company_percentage=int(INCLUDE_COMPANY_RATIO * 100),
        variety_factor=variety_factor,
        excluded_emails_text=excluded_emails_text,
    )


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), reraise=True)
async def generate_realistic_customers(used_emails: set[str], used_phones: set[str], used_names: set[str], used_companies: set[str], batch_size: int | None = None) -> dict:
    """Generate realistic customer data using Anthropic API."""
    batch_size = batch_size or CUSTOMERS_BATCH_SIZE

    prompt = create_customers_prompt(used_emails, batch_size)
    response_data = await make_anthropic_request(prompt=prompt, api_key=settings.ANTHROPIC_API_KEY, max_tokens=4000)

    if not response_data:
        raise Exception("Failed to get response from Anthropic API")

    customers = parse_anthropic_response(response_data)

    if not customers:
        raise Exception("Invalid customer data format from Anthropic")

    required_fields = ["email", "first_name"]
    valid_customers = validate_data_structure(customers, required_fields)

    if not valid_customers:
        raise Exception("No valid customers generated")

    unique_customers: list[dict] = []
    duplicates_found: list[str] = []
    new_used_emails = used_emails.copy()
    new_used_phones = used_phones.copy()
    new_used_names = used_names.copy()
    new_used_companies = used_companies.copy()

    for customer in valid_customers:
        email_lower = customer["email"].strip().lower()
        if email_lower in new_used_emails:
            duplicates_found.append(email_lower)
            continue

        phone = customer.get("phone")
        if phone:
            phone = normalize_phone(phone)
            if phone and phone in new_used_phones:
                duplicates_found.append(f"phone:{phone}")
                continue
            if phone:
                new_used_phones.add(phone)

        first_name = customer.get("first_name")
        last_name = customer.get("last_name")
        if first_name and last_name:
            name_combo = f"{first_name.lower().strip()} {last_name.lower().strip()}"
            if name_combo in new_used_names:
                duplicates_found.append(name_combo)
                continue
            new_used_names.add(name_combo)

        company = customer.get("company_name")
        if company:
            company_lower = company.lower().strip()
            if company_lower in new_used_companies:
                duplicates_found.append(company_lower)
                continue
            new_used_companies.add(company_lower)

        new_used_emails.add(email_lower)
        unique_customers.append(customer)

    if duplicates_found:
        logger.warning(f"Filtered {len(duplicates_found)} duplicates")

    if not unique_customers:
        raise Exception("No unique customers generated")

    logger.info(f"Generated {len(unique_customers)} unique customers")

    return {
        "unique_customers": unique_customers,
        "updated_used_emails": new_used_emails,
        "updated_used_phones": new_used_phones,
        "updated_used_names": new_used_names,
        "updated_used_companies": new_used_companies,
    }


async def generate_customers(n_customers: int | None = None) -> dict:
    target_count = n_customers or DEFAULT_CUSTOMERS_COUNT
    logger.info(f"Starting customers generation - Target: {target_count}, Batch size: {CUSTOMERS_BATCH_SIZE}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    existing_data = load_existing_customers()
    generated_customers = existing_data["generated_customers"]
    used_emails = existing_data["used_emails"]
    used_phones = existing_data["used_phones"]
    used_names = existing_data["used_names"]
    used_companies = existing_data["used_companies"]

    try:
        total_generated = 0
        total_processed = 0

        while total_processed < target_count:
            remaining_count = target_count - total_processed
            current_batch_size = min(CUSTOMERS_BATCH_SIZE, remaining_count)

            try:
                generation_result = await generate_realistic_customers(
                    used_emails=used_emails, used_phones=used_phones, used_names=used_names, used_companies=used_companies, batch_size=current_batch_size
                )

                unique_customers = generation_result["unique_customers"]
                generated_customers.extend(unique_customers)
                used_emails = generation_result["updated_used_emails"]
                used_phones = generation_result["updated_used_phones"]
                used_names = generation_result["updated_used_names"]
                used_companies = generation_result["updated_used_companies"]

                total_generated += len(unique_customers)
                total_processed += len(unique_customers)

            except Exception as e:
                logger.error(f"Batch failed: {e}")
                break

        if generated_customers:
            save_to_json(generated_customers, CUSTOMERS_FILEPATH)
            logger.info(f"Saved {len(generated_customers)} customers to {CUSTOMERS_FILEPATH}")

        logger.info(f"Generated {total_processed}/{total_generated} customers - Success rate: {(total_processed / total_generated) * 100:.1f}%")

        return {
            "total_processed": total_processed,
            "total_generated": total_generated,
            "customers": generated_customers,
        }

    except Exception as error:
        logger.error(f"Fatal error during generation: {error}")
        if generated_customers:
            save_to_json(generated_customers, CUSTOMERS_FILEPATH)
        raise


async def customers(n_customers: int | None = None):
    result = await generate_customers(n_customers)
    logger.info(f"Generated {result['total_processed']} customers successfully")
    return result


if __name__ == "__main__":
    asyncio.run(customers())
