import asyncio
import json
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.core.labels import LABELS_FILE_PATH
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
macros_file = settings.DATA_PATH / "generated" / "macros.json"


class MacroAction(BaseModel):
    action_name: str = Field(description="The name of the action to perform")
    action_params: list[str | int] = Field(description="Parameters for the action")


class Macro(BaseModel):
    name: str = Field(description="The name of the macro")
    actions: list[MacroAction] = Field(description="List of actions the macro performs")
    visibility: str = Field(description="Visibility of the macro (global, personal, etc.)")
    created_at: datetime = Field(description="When the macro was created")
    updated_at: datetime = Field(description="When the macro was last updated")


class MacroList(BaseModel):
    macros: list[Macro] = Field(description="A list of macros")


async def generate_macros(number_of_macros: int):
    """Generate specified number of macros using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    macros_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing macros.json as reference
    reference_macros_file = Path(__file__).parent.parent.joinpath("data", "macros.json")
    reference_macros = []
    try:
        with reference_macros_file.open(encoding="utf-8") as f:
            reference_macros = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Reference macros file not found: {reference_macros_file}")

    # Load available labels from the generated labels.json file
    labels_file = LABELS_FILE_PATH
    available_labels = []
    try:
        with labels_file.open(encoding="utf-8") as f:
            labels_data = json.load(f)
            available_labels = [label["title"] for label in labels_data]
            logger.info(f"Loaded {len(available_labels)} available labels: {available_labels}")
    except FileNotFoundError:
        logger.warning(f"Labels file not found: {labels_file}")
        logger.warning("Using default labels for macro generation")
        available_labels = ["bug_report", "technical_support", "sales_inquiry", "billing_issue"]

    logger.start(f"Generating {number_of_macros} macros")

    # Generate macros using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            macros_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates realistic macro data for Chatwoot. Always generate the EXACT number of macros requested.",
                    },
                    {
                        "role": "user",
                        "content": f"""Generate EXACTLY {number_of_macros} macros for a Chatwoot customer support system of {settings.COMPANY_NAME}, a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {number_of_macros} macros, no more, no less.
                        
                        Learn from these example macros to understand the structure and available actions:
                        ```json
                        {json.dumps(reference_macros, indent=2)}
                        ```
                        
                        From the examples, I can see macros are automated workflows with these action types:
                        
                        **Team Assignment Actions:**
                        - assign_team: [team_id] - Assigns conversation to specific team
                        
                        **Label Management Actions:**
                        - add_label: ["label_name"] - Adds labels from the available labels list
                        - remove_label: ["label_name"] - Removes existing labels
                        
                        **IMPORTANT - Available Labels:**
                        You MUST only use labels from this exact list when using add_label or remove_label actions:
                        {available_labels}
                        
                        **Communication Actions:**
                        - send_message: ["message_text"] - Sends message to customer
                        - add_private_note: ["note_text"] - Adds internal note for agents
                        - send_attachment: ["url"] - Sends file attachment
                        
                        **Conversation Management Actions:**
                        - resolve_conversation: [] - Marks conversation as resolved
                        - snooze_conversation: [minutes] - Snoozes for specified minutes
                        - mute_conversation: [] - Mutes conversation notifications
                        - change_priority: ["low"|"medium"|"high"|"urgent"] - Sets priority level
                        
                        **Common Macro Categories:**
                        - **Escalation**: Bug reports, technical issues, urgent matters
                        - **Routing**: Sales leads, product feedback, specific departments
                        - **Resolution**: Closing tickets, resolving issues, follow-ups
                        - **Customer Journey**: Onboarding, renewal reminders, surveys
                        - **Workflow Management**: Status updates, team assignments, prioritization
                        
                        **Requirements:**
                        - Use descriptive names that clearly indicate the macro's purpose
                        - Combine multiple actions for comprehensive workflows
                        - Use realistic team IDs (1-6) for assign_team actions
                        - ONLY use labels from the provided available labels list: {available_labels}
                        - Add private notes for internal documentation
                        - Use professional, helpful messages for customer communication
                        - Set visibility to "global" for team-wide access
                        - Make macros specific to {settings.COMPANY_NAME} ({settings.DATA_THEME_SUBJECT}) context when relevant
                        
                        Focus on creating macros that automate common support workflows and save agents time while maintaining quality service.""",
                    },
                ],
                response_format=MacroList,
            )

            macros_data = macros_response.choices[0].message.parsed.macros

            # Validate we got the correct number
            if len(macros_data) >= number_of_macros:
                # Trim to exact number if we got more
                macros_data = macros_data[:number_of_macros]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(macros_data)} macros, need {number_of_macros}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_macros} macros after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate macros after {max_retries} attempts")
                return

    # Add timestamps to each macro
    for macro in macros_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        macro.created_at = created_at
        macro.updated_at = updated_at

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_macros = [macro.model_dump(mode="json") for macro in macros_data]

    # Store macros in JSON file
    with macros_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_macros, f, indent=2, default=str)
        logger.succeed(f"Stored {len(macros_data)} macros in {macros_file}")


async def seed_macros():
    """Seed macros from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        macros = None
        try:
            with macros_file.open(encoding="utf-8") as f:
                macros = [Macro(**macro) for macro in json.load(f)]
                logger.info(f"Loaded {len(macros)} macros from {macros_file}")
        except FileNotFoundError:
            logger.error(f"Macros file not found: {macros_file}")
            logger.error("Please run generate_macros() first to create the macros file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {macros_file}")
            return

        if macros is None:
            logger.error("No macros loaded from file")
            return

        # Create async tasks for adding macros concurrently
        async def add_single_macro(macro: Macro) -> dict | None:
            """Add a single macro and return the macro if successful, None if failed."""
            try:
                # Convert Pydantic model to dict for API call (exclude timestamps)
                macro_config = macro.model_dump(exclude={"created_at", "updated_at"})

                await client.add_macro(macro_config)
                return macro.model_dump()
            except Exception as e:
                logger.error(f"Error adding macro {macro.name}: {e}")
                return None

        # Run all add_macro calls concurrently
        logger.start(f"Adding {len(macros)} macros concurrently...")
        results = await asyncio.gather(*[add_single_macro(macro) for macro in macros], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added macros
        added_macros = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.succeed(f"Successfully added {len(added_macros)} out of {len(macros)} macros")


async def insert_macros():
    """Legacy function - generates macros and seeds them into Chatwoot."""
    # For backward compatibility, use the existing macros.json file
    reference_macros_file = Path(__file__).parent.parent.joinpath("data", "macros.json")
    try:
        with reference_macros_file.open(encoding="utf-8") as f:
            reference_macros = json.load(f)
        await generate_macros(len(reference_macros))
    except FileNotFoundError:
        logger.warning("Reference macros.json not found, generating 12 macros")
        await generate_macros(12)

    await seed_macros()


async def delete_macros():
    async with ChatwootClient() as client:
        macros = await client.list_macros()

        for macro in macros:
            try:
                await client.delete_macro(macro["id"])
                logger.info(f"Deleted macro: {macro['name']}")
            except Exception as e:
                logger.error(f"Error deleting macro: {e}")
