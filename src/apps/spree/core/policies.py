import json
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from apps.spree.config.settings import settings
from apps.spree.utils.ai import instructor_client
from common.logger import Logger


logger = Logger()

POLICIES = ["customer_privacy_policy", "customer_returns_policy", "customer_shipping_policy", "customer_terms_of_service"]


class PolicyResponse(BaseModel):
    """Simple response format for generated policies."""

    customer_privacy_policy: str
    customer_returns_policy: str
    customer_shipping_policy: str
    customer_terms_of_service: str


async def generate_policies() -> dict[str, str]:
    """Generate e-commerce policies as HTML-formatted rich text."""

    clean_store_name = re.sub(r"[^a-zA-Z0-9]", "", settings.SPREE_STORE_NAME).lower()
    # Check if policies file already exists
    policies_file = settings.DATA_PATH / "policies.json"
    if policies_file.exists():
        logger.info(f"Policies file already exists at {policies_file}, loading existing policies")
        try:
            with Path.open(policies_file, encoding="utf-8") as f:
                existing_policies = json.load(f)
            logger.succeed(f"Loaded {len(existing_policies)} existing policies")
            return existing_policies
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load existing policies file: {e}, generating new policies")

    if not settings.OPENAI_API_KEY:
        logger.error("OpenAI API key is not configured")
        raise ValueError("OpenAI API key is required for policy generation")

    logger.info("Generating e-commerce policies...")

    try:
        system_prompt = f"""You are an expert legal writer specializing in e-commerce policies. 
        Generate comprehensive, legally sound policies for an online store in HTML format.
        
        Store Details:
        - Store Name: {settings.SPREE_STORE_NAME}
        - Store Theme: {settings.DATA_THEME_SUBJECT}
        - Store URL: https://{clean_store_name}.com
        - Contact Email: contact@{clean_store_name}.com
        - Today's Date: {datetime.now().strftime("%Y-%m-%d")}
        
        Generate HTML-formatted policies for:
        1. customer_privacy_policy - covering data collection, usage, cookies, third-party services
        2. customer_returns_policy - covering return conditions, timeframes, refund process
        3. customer_shipping_policy - covering shipping methods, delivery times, costs, international shipping
        4. customer_terms_of_service - covering user obligations, limitations, dispute resolution
        
        Format each policy as rich HTML with:
        - Proper headings but only use h2
        - Paragraphs and lists
        - Professional styling
        - Clear structure and sections
        - Include effective dates (use current date)
        
        Make policies legally compliant, professional, and specific to the store's theme."""

        user_prompt = f"""Generate comprehensive HTML-formatted e-commerce policies for {settings.SPREE_STORE_NAME}, 
        a {settings.DATA_THEME_SUBJECT}. The store operates at {settings.SPREE_URL} and can be contacted at {settings.SPREE_ADMIN_EMAIL}.
        
        Return the policies as HTML-formatted rich text that can be directly used on a website."""

        policies_response = await instructor_client.chat.completions.create(
            model="claude-3-5-haiku-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=PolicyResponse,
            temperature=0.7,
            max_tokens=8192,
        )

        if policies_response:
            policies_dict = policies_response.model_dump()

            # Save to file
            settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
            with Path.open(policies_file, "w", encoding="utf-8") as f:
                json.dump(policies_dict, f, indent=2, ensure_ascii=False)

            logger.succeed(f"Successfully generated and saved {len(policies_dict)} policies to {policies_file}")
            for policy_name in policies_dict:
                logger.info(f"Generated {policy_name}")
            return policies_dict
        else:
            logger.error("Failed to parse policy response from OpenAI")
            raise ValueError("Failed to generate policies")

    except Exception as e:
        logger.error(f"Error generating policies: {e}")
        raise


async def insert_policies():
    """Insert policies into the database."""
    from apps.spree.utils.database import db_client

    logger.start("Updating policies in action_text_rich_texts table...")

    try:
        # Load policies from JSON file
        policies_file = settings.DATA_PATH / "policies.json"
        if not policies_file.exists():
            logger.error(f"Policies file not found at {policies_file}. Run generate command first.")
            raise FileNotFoundError("Policies file not found")

        with Path.open(policies_file, encoding="utf-8") as f:
            policies = json.load(f)

        logger.info(f"Loaded {len(policies)} policies from {policies_file}")

        # Update each policy in the database
        updated_count = 0
        for policy_name, policy_body in policies.items():
            try:
                # Check if record exists
                existing_record = await db_client.fetchrow("SELECT id FROM action_text_rich_texts WHERE name = $1", policy_name)

                if existing_record:
                    # Update existing record
                    await db_client.execute(
                        """
                        UPDATE action_text_rich_texts 
                        SET body = $1, updated_at = NOW() 
                        WHERE name = $2
                        """,
                        policy_body,
                        policy_name,
                    )
                else:
                    # Insert new record (assuming record_type='Spree::Store' and record_id=1)
                    await db_client.execute(
                        """
                        INSERT INTO action_text_rich_texts (name, body, record_type, record_id, created_at, updated_at, locale)
                        VALUES ($1, $2, $3, $4, NOW(), NOW(), $5)
                        """,
                        policy_name,
                        policy_body,
                        "Spree::Store",
                        1,
                        "en",
                    )
                    logger.info(f"Inserted new policy: {policy_name}")

                updated_count += 1

            except Exception as e:
                logger.error(f"Failed to update policy {policy_name}: {e}")
                continue

        logger.succeed(f"Successfully updated {updated_count} policies in the database")

    except Exception as e:
        logger.error(f"Error updating policies in database: {e}")
        raise
