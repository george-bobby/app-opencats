import asyncio
import json
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.database import AsyncPostgresClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
CUSTOM_ATTRIBUTE_FILE_PATH = settings.DATA_PATH / "generated" / "custom_attributes.json"


class CustomAttribute(BaseModel):
    attribute_display_name: str = Field(description="Display name of the custom attribute")
    attribute_description: str = Field(description="Description of the custom attribute")
    attribute_model: int = Field(description="Model type: 0 for contact, 1 for conversation")
    attribute_display_type: int = Field(description="Display type: 1=text, 4=link, 5=date, 6=list, 7=checkbox")
    attribute_key: str = Field(description="Unique key for the attribute in snake_case")
    attribute_values: list[str] = Field(description="List of possible values for list type attributes")
    regex_pattern: str | None = Field(description="Regex pattern for validation")
    regex_cue: str | None = Field(description="Regex validation hint")
    created_at: datetime = Field(description="When the attribute was created")
    updated_at: datetime = Field(description="When the attribute was last updated")


class CustomAttributeList(BaseModel):
    custom_attributes: list[CustomAttribute] = Field(description="A list of custom attributes")


async def generate_custom_attributes(number_of_attributes: int):
    """Generate specified number of custom attributes using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    CUSTOM_ATTRIBUTE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing custom_attributes.json as reference
    reference_attributes_file = Path(__file__).parent.parent.joinpath("data", "custom_attributes.json")
    reference_attributes = []
    try:
        with reference_attributes_file.open(encoding="utf-8") as f:
            reference_attributes = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Reference custom attributes file not found: {reference_attributes_file}")

    logger.start(f"Generating {number_of_attributes} custom attributes")

    # Generate custom attributes using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            attributes_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates realistic custom attribute data for Chatwoot. Always generate the EXACT number of custom attributes requested."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"""Generate EXACTLY {number_of_attributes} custom attributes for a Chatwoot customer support system of a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {number_of_attributes} custom attributes, no more, no less.
                        
                        Learn from these example custom attributes to understand the structure and types:
                        ```json
                        {json.dumps(reference_attributes, indent=2)}
                        ```
                        
                        From the examples, I can see different types of custom attributes:
                        
                        **Text Attributes (attribute_display_type: 1):**
                        - Numeric values (lifetime_value, revenue, order_count)
                        - Free-form descriptions (most_ordered_item, feedback_sentiment, notes)
                        - IDs or codes (customer_id, ticket_id, reference_number)
                        - Specific product names or unique identifiers
                        
                        **List Attributes (attribute_display_type: 6):**
                        - Staff assignments (account_manager, sales_rep, support_agent)
                        - Categories and tiers (customer_tier, subscription_plan, priority_level)
                        - Status and levels (engagement_level, customer_type, issue_category)
                        - Communication preferences (preferred_channel, contact_method)
                        - Include 3-5 relevant attribute_values for each list
                        
                        **Checkbox Attributes (attribute_display_type: 7):**
                        - Boolean flags (requires_follow_up, is_premium_customer, email_notifications_enabled)
                        
                        **Date Attributes (attribute_display_type: 5):**
                        - Date fields (customer_since, last_purchase_date, contract_expiry)
                        
                        **Link Attributes (attribute_display_type: 4):**
                        - URL fields (order_link, profile_url, documentation_link)
                        
                        **Requirements:**
                        - attribute_model should be 0 (contact) or 1 (conversation)
                        - attribute_key should be snake_case version of display_name
                        - attribute_description should explain the purpose
                        - Make attributes relevant to {settings.DATA_THEME_SUBJECT} context
                        - Use appropriate display types:
                          * Use type 1 for text fields (numeric values, descriptions, IDs, unique identifiers)
                          * Use type 6 for lists with predefined options (staff names, categories, tiers, statuses)
                          * Use type 7 for checkboxes/boolean flags (leave attribute_values empty)
                          * Use type 5 for dates (leave attribute_values empty)
                          * Use type 4 for URLs/links (leave attribute_values empty)
                        - For list attributes, provide meaningful attribute_values array with 3-5 options
                        - For non-list attributes, leave attribute_values as empty array
                        - Leave regex_pattern and regex_cue as null unless specific validation needed
                        
                        Examples of correct typing:
                        - "Account Manager" → attribute_display_type: 6 (list with values like ["John Smith", "Sarah Johnson", "Mike Wilson"])
                        - "Lifetime Value" → attribute_display_type: 1 (text for numeric input)
                        - "Customer Tier" → attribute_display_type: 6 (list with values like ["Bronze", "Silver", "Gold", "Platinum"])
                        - "Requires Follow-up" → attribute_display_type: 7 (checkbox)
                        - "Customer Since" → attribute_display_type: 5 (date)
                        - "Order History Link" → attribute_display_type: 4 (link)""",
                    },
                ],
                response_format=CustomAttributeList,
            )

            attributes_data = attributes_response.choices[0].message.parsed.custom_attributes

            # Validate we got the correct number
            if len(attributes_data) >= number_of_attributes:
                # Trim to exact number if we got more
                attributes_data = attributes_data[:number_of_attributes]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(attributes_data)} custom attributes, need {number_of_attributes}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_attributes} custom attributes after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate custom attributes after {max_retries} attempts")
                return

    # Add timestamps to each attribute
    for attribute in attributes_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        attribute.created_at = created_at
        attribute.updated_at = updated_at

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_attributes = [attribute.model_dump(mode="json") for attribute in attributes_data]

    # Store custom attributes in JSON file
    with CUSTOM_ATTRIBUTE_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable_attributes, f, indent=2, default=str)
        logger.succeed(f"Stored {len(attributes_data)} custom attributes in {CUSTOM_ATTRIBUTE_FILE_PATH}")


async def seed_custom_attributes():
    """Seed custom attributes from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        custom_attributes = None
        try:
            with CUSTOM_ATTRIBUTE_FILE_PATH.open(encoding="utf-8") as f:
                custom_attributes = [CustomAttribute(**attr) for attr in json.load(f)]
                logger.info(f"Loaded {len(custom_attributes)} custom attributes from {CUSTOM_ATTRIBUTE_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Custom attributes file not found: {CUSTOM_ATTRIBUTE_FILE_PATH}")
            logger.error("Please run generate_custom_attributes() first to create the custom attributes file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {CUSTOM_ATTRIBUTE_FILE_PATH}")
            return

        if custom_attributes is None:
            logger.error("No custom attributes loaded from file")
            return

        # Create async tasks for adding custom attributes concurrently
        async def add_single_custom_attribute(attribute: CustomAttribute) -> dict | None:
            """Add a single custom attribute and return the attribute if successful, None if failed."""
            try:
                # Convert Pydantic model to dict for API call (exclude timestamps)
                attribute_config = attribute.model_dump(exclude={"created_at", "updated_at"})

                await client.add_custom_attribute(attribute_config)
                logger.info(f"Added custom attribute {attribute.attribute_display_name}")
                return attribute.model_dump()
            except Exception as e:
                logger.error(f"Error adding custom attribute {attribute.attribute_display_name}: {e}")
                return None

        # Run all add_custom_attribute calls concurrently
        logger.info(f"Adding {len(custom_attributes)} custom attributes concurrently...")
        results = await asyncio.gather(*[add_single_custom_attribute(attr) for attr in custom_attributes], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added attributes
        added_attributes = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.info(f"Successfully added {len(added_attributes)} out of {len(custom_attributes)} custom attributes")

        # Randomize timestamps for automation_rules table
        logger.info("Randomizing automation_rules timestamps...")
        automation_rules = await AsyncPostgresClient.fetch("SELECT id FROM automation_rules ORDER BY id")

        if automation_rules:
            for rule in automation_rules:
                rule_id = rule["id"]

                # Generate realistic timestamps: created_at in the past, updated_at between created_at and now
                created_at = faker.date_time_between(start_date="-2y", end_date="-1m")
                updated_at = faker.date_time_between(start_date=created_at, end_date="now")

                update_query = """
                    UPDATE automation_rules 
                    SET created_at = $1, updated_at = $2 
                    WHERE id = $3
                """
                await AsyncPostgresClient.execute(update_query, created_at, updated_at, rule_id)

            logger.info(f"Successfully randomized timestamps for {len(automation_rules)} automation rules")
        else:
            logger.info("No automation rules found to update timestamps")


async def insert_custom_attributes():
    """Legacy function - generates custom attributes and seeds them into Chatwoot."""
    # For backward compatibility, use the existing custom_attributes.json file
    reference_attributes_file = Path(__file__).parent.parent.joinpath("data", "custom_attributes.json")
    try:
        with reference_attributes_file.open(encoding="utf-8") as f:
            reference_attributes = json.load(f)
        await generate_custom_attributes(len(reference_attributes))
    except FileNotFoundError:
        logger.warning("Reference custom_attributes.json not found, generating 10 custom attributes")
        await generate_custom_attributes(10)

    await seed_custom_attributes()
