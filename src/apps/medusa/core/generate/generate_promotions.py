import asyncio
import json
import re
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apps.medusa.config.constants import (
    DEFAULT_PROMOTIONS_COUNT,
    PROMOTION_TYPES,
    PROMOTIONS_FILEPATH,
)
from apps.medusa.config.settings import settings
from apps.medusa.core.generate.prompts.generate_promotions_prompts import PROMOTIONS_PROMPT
from apps.medusa.utils.data_utils import load_existing_data
from common.anthropic_client import make_anthropic_request, validate_anthropic_config
from common.logger import logger
from common.save_to_json import save_to_json


def load_existing_promotions():
    existing = load_existing_data(filepath=PROMOTIONS_FILEPATH, unique_fields=["code"], track_all=True)

    return {
        "used_codes": existing["used_identifiers"].get("code", set()),
        "generated_promotions": existing["items"],
        "all_generated_promotions": existing["items"].copy() if existing["items"] else [],
    }


def generate_unique_code(base_code: str, used_codes: set[str]) -> tuple[str, set[str]]:
    code = base_code.upper()
    counter = 1
    new_used_codes = used_codes.copy()

    while code in new_used_codes:
        code = f"{base_code}{counter}".upper()
        counter += 1

    new_used_codes.add(code)
    return code, new_used_codes


def extract_json_from_response(text: str) -> list[dict]:
    """Extract JSON array from API response."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    json_start = text.find("[")
    if json_start > 0:
        text = text[json_start:]

    json_end = text.rfind("]")
    if json_end > 0:
        text = text[: json_end + 1]

    text = re.sub(r",(\s*[}\]])", r"\1", text)
    text = re.sub(r"}\s*\n\s*{", "},\n  {", text)

    return json.loads(text.strip())


def create_promotions_prompt(promo_type: dict[str, Any], count: int, used_codes: set[str]) -> str:
    """Create prompt for promotion generation."""
    excluded_codes = ", ".join(list(used_codes)[-10:]) if used_codes else "none"

    # Build buyget fields if applicable
    buyget_fields = ""
    if promo_type.get("is_buyget"):
        buyget_fields = """- is_buyget: true
   - buy_rules_min_quantity: 1-3
   - apply_to_quantity: 1"""

    # Determine campaign requirement text
    campaign_requirement = "Only if needs_campaign is true" if promo_type.get("needs_campaign") else "MUST be null"

    # Determine max_quantity requirement
    max_quantity_requirement = '1-10 if allocation is "each"' if promo_type["allocation"] == "each" else "null"

    return PROMOTIONS_PROMPT.format(
        count=count,
        promo_type_name=promo_type["name"],
        promo_type_description=promo_type["description"],
        excluded_codes=excluded_codes,
        promo_type_type=promo_type["type"],
        is_automatic=str(promo_type.get("is_automatic", False)).lower(),
        campaign_requirement=campaign_requirement,
        target_type=promo_type["target_type"],
        allocation=promo_type["allocation"],
        value_type=promo_type["value_type"],
        needs_currency=str(promo_type.get("needs_currency", False)).lower(),
        max_quantity_requirement=max_quantity_requirement,
        buyget_fields=buyget_fields,
    )


@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), retry=retry_if_exception_type(Exception))
async def generate_realistic_promotions(promo_type: dict[str, Any], count: int, used_codes: set[str], all_generated_promotions: list[dict], max_attempts: int = 3) -> dict:  # noqa: ARG001
    """Generate realistic promotion data using Anthropic API."""
    try:
        prompt = create_promotions_prompt(promo_type, count, used_codes)
        estimated_tokens = count * 400 + 1000
        max_tokens = min(estimated_tokens, 4000)

        response_data = await make_anthropic_request(prompt=prompt, api_key=settings.ANTHROPIC_API_KEY, max_tokens=max_tokens)

        if not response_data:
            raise Exception("Failed to get response from Anthropic API")

        content = response_data["content"][0]["text"]
        promotions = extract_json_from_response(content)

        if not promotions:
            raise Exception("Invalid promotion data format from Anthropic")

        unique_promotions = []
        duplicates_found = []
        new_used_codes = used_codes.copy()
        new_all_promotions = all_generated_promotions.copy()

        for promo in promotions:
            code = promo.get("code", "PROMO").upper()
            if code in new_used_codes:
                code, new_used_codes = generate_unique_code(code, new_used_codes)
                promo["code"] = code
                duplicates_found.append(code)
            else:
                new_used_codes.add(code)

            unique_promotions.append(promo)
            new_all_promotions.append(promo)

        if duplicates_found:
            logger.debug(f"Regenerated {len(duplicates_found)} duplicate codes")

        if not unique_promotions:
            raise Exception("No unique promotions generated")

        return {
            "unique_promotions": unique_promotions,
            "updated_used_codes": new_used_codes,
            "updated_all_promotions": new_all_promotions,
        }

    except Exception as error:
        logger.error(f"Generation attempt failed: {error}")
        raise


async def generate_promotions(count: int | None = None) -> dict:
    """Generate promotions and save to file."""
    target_count = count or DEFAULT_PROMOTIONS_COUNT
    logger.info(f"Starting promotions generation - Target: {target_count}")

    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    validate_anthropic_config(settings.ANTHROPIC_API_KEY)

    existing_data = load_existing_promotions()
    generated_promotions = existing_data["generated_promotions"]
    all_generated_promotions = existing_data["all_generated_promotions"]
    used_codes = existing_data["used_codes"]

    try:
        promotion_types = PROMOTION_TYPES
        promos_per_type = target_count // len(promotion_types)
        remainder = target_count % len(promotion_types)

        total_generated = 0
        total_processed = 0
        consecutive_failures = 0
        max_consecutive_failures = 3

        for idx, promo_type in enumerate(promotion_types):
            count = promos_per_type + (1 if idx < remainder else 0)
            if count == 0:
                continue

            logger.info(f"Type {idx + 1}/{len(promotion_types)}: {promo_type['name']} - Generating {count} promotions")

            try:
                generation_result = await generate_realistic_promotions(promo_type=promo_type, count=count, used_codes=used_codes, all_generated_promotions=all_generated_promotions)

                unique_promotions = generation_result["unique_promotions"]
                generated_promotions.extend(unique_promotions)
                all_generated_promotions = generation_result["updated_all_promotions"]
                used_codes = generation_result["updated_used_codes"]

                total_generated += len(unique_promotions)
                total_processed += len(unique_promotions)
                consecutive_failures = 0

                logger.info(f"  Generated {len(unique_promotions)} promotions (Total: {total_processed}/{target_count})")

            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Type {promo_type['name']} failed: {e}")

                if consecutive_failures >= max_consecutive_failures:
                    logger.error("Too many consecutive failures. Stopping generation.")
                    break

        if generated_promotions:
            save_to_json(generated_promotions, PROMOTIONS_FILEPATH)
            logger.info(f"Saved {len(generated_promotions)} promotions to {PROMOTIONS_FILEPATH}")

        success_rate = (total_processed / total_generated * 100) if total_generated > 0 else 0
        logger.info(f"\nGeneration complete: {total_processed}/{total_generated} ({success_rate:.1f}% success rate)")

        return {
            "total_processed": total_processed,
            "total_generated": total_generated,
            "promotions": generated_promotions,
        }

    except Exception as error:
        logger.error(f"Fatal error: {error}")
        if generated_promotions:
            save_to_json(generated_promotions, PROMOTIONS_FILEPATH)
        raise


async def promotions(count: int | None = None):
    result = await generate_promotions(count)
    return result


if __name__ == "__main__":
    import sys

    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(promotions(count))
