import asyncio
import json
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
LABELS_FILE_PATH = settings.DATA_PATH / "generated" / "labels.json"


class Label(BaseModel):
    title: str = Field(description="The title of the label, has to be in snake_case")
    description: str = Field(description="The description of the label")
    color: str = Field(description="The color of the label in hex format")
    show_on_sidebar: bool = Field(description="Whether to show the label on sidebar")
    created_at: datetime = Field(description="When the label was created")
    updated_at: datetime = Field(description="When the label was last updated")


class LabelList(BaseModel):
    labels: list[Label] = Field(description="A list of labels")


async def generate_labels(number_of_labels: int):
    """Generate specified number of labels using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    LABELS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger.start(f"Generating {number_of_labels} labels")

    # Generate labels using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            labels_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates realistic label data for Chatwoot. Always generate the EXACT number of labels requested.",
                    },
                    {
                        "role": "user",
                        "content": f"""Generate EXACTLY {number_of_labels} labels for a Chatwoot customer support system of {settings.COMPANY_NAME}, a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {number_of_labels} labels, no more, no less.
                        
                        Create labels that would be useful for organizing and categorizing customer conversations. Include:
                        
                        **Category Labels:**
                        - Technical issues (bug_report, technical_support, integration_help)
                        - Business inquiries (sales_inquiry, pricing_question, partnership)
                        - Account management (billing_issue, account_setup, subscription)
                        
                        **Department Labels:**
                        - technical_team, sales_team, billing_team, product_team
                        - management_review, legal_review
                        
                        **Customer Type Labels:**
                        - vip_customer, new_customer, enterprise_client
                        - trial_user, premium_subscriber

                        Excludes these labels:
                            **Priority Labels:**
                            - urgent, high_priority, escalated, critical
                            - routine, low_priority, follow_up
                            
                            **Status Labels:**
                            - resolved, pending, in_progress, waiting_for_customer
                            - needs_escalation, under_review, closed

                        
                        Each label should:
                        - Have a descriptive title (kebab-case or snake_case preferred)
                        - Include a helpful description explaining when to use it
                        - Use appropriate hex colors (#format)
                        - Be relevant to {settings.COMPANY_NAME} ({settings.DATA_THEME_SUBJECT}) context
                        - Set show_on_sidebar to true for important labels, false for less common ones""",
                    },
                ],
                response_format=LabelList,
            )

            labels_data = labels_response.choices[0].message.parsed.labels

            # Validate we got the correct number
            if len(labels_data) >= number_of_labels:
                # Trim to exact number if we got more
                labels_data = labels_data[:number_of_labels]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(labels_data)} labels, need {number_of_labels}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_labels} labels after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate labels after {max_retries} attempts")
                return

    # Add timestamps to each label
    for label in labels_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        label.created_at = created_at
        label.updated_at = updated_at

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_labels = [label.model_dump(mode="json") for label in labels_data]

    # Store labels in JSON file
    with LABELS_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable_labels, f, indent=2, default=str)
        logger.succeed(f"Stored {len(labels_data)} labels in {LABELS_FILE_PATH}")


async def seed_labels():
    """Seed labels from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        labels = None
        try:
            with LABELS_FILE_PATH.open(encoding="utf-8") as f:
                labels = [Label(**label) for label in json.load(f)]
                logger.info(f"Loaded {len(labels)} labels from {LABELS_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Labels file not found: {LABELS_FILE_PATH}")
            logger.error("Please run generate_labels() first to create the labels file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {LABELS_FILE_PATH}")
            return

        if labels is None:
            logger.error("No labels loaded from file")
            return

        # Create async tasks for adding labels concurrently
        async def add_single_label(label: Label) -> dict | None:
            """Add a single label and return the label if successful, None if failed."""
            try:
                await client.add_label(
                    title=label.title,
                    description=label.description,
                    color=label.color,
                    show_on_sidebar=label.show_on_sidebar,
                )
                return label.model_dump()
            except Exception as e:
                logger.error(f"Error adding label {label.title}: {e}")
                return None

        # Run all add_label calls concurrently
        logger.start(f"Adding {len(labels)} labels concurrently...")
        results = await asyncio.gather(*[add_single_label(label) for label in labels], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added labels
        added_labels = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.succeed(f"Successfully added {len(added_labels)} out of {len(labels)} labels")


async def insert_labels(number_of_labels: int):
    """Legacy function - generates labels and seeds them into Chatwoot."""
    await generate_labels(number_of_labels)
    await seed_labels()


async def delete_labels():
    async with ChatwootClient() as client:
        labels = await client.list_labels()

        for label in labels:
            await client.delete_label(label["id"])
            logger.info(f"Deleted label {label['title']}")
