import asyncio
import json
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.core.agents import AGENTS_FILE_PATH
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


inboxes_file = settings.DATA_PATH / "generated" / "inboxes.json"
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class WebWidgetChannel(BaseModel):
    type: str = Field(description="Channel type (web_widget)")  # noqa: A003, RUF100
    website_url: str = Field(description="Website URL for the widget")
    widget_color: str = Field(description="Hex color code for the widget")
    welcome_title: str = Field(description="Welcome title for the widget")
    welcome_tagline: str = Field(description="Welcome tagline for the widget")


class EmailChannel(BaseModel):
    type: str = Field(description="Channel type (email)")  # noqa: A003, RUF100
    email: str = Field(description="Email address for the inbox")
    imap_enabled: bool = Field(default=False, description="Whether IMAP is enabled, always false")
    imap_address: str = Field(description="IMAP server address")
    imap_port: int = Field(description="IMAP server port")
    imap_login: str = Field(description="IMAP login username")
    imap_password: str = Field(description="IMAP login password")


class APIChannel(BaseModel):
    type: str = Field(description="Channel type (api)")  # noqa: A003, RUF100
    webhook_url: str = Field(description="Webhook URL for API integration")


class SMSProviderConfig(BaseModel):
    api_key: str = Field(description="API key for SMS provider")
    api_secret: str = Field(description="API secret for SMS provider")
    application_id: str = Field(description="Application ID for SMS provider")
    account_id: str = Field(description="Account ID for SMS provider")


class SMSChannel(BaseModel):
    type: str = Field(description="Channel type (sms)")  # noqa: A003, RUF100
    phone_number: str = Field(description="Phone number for SMS")
    provider_config: SMSProviderConfig = Field(description="SMS provider configuration")


class CSATSurveyRules(BaseModel):
    operator: str = Field(description="Survey rule operator (e.g., 'contains')", default="contains")
    values: list[str] = Field(description="Survey rule values", default_factory=list)


class CSATConfig(BaseModel):
    display_type: str = Field(description="CSAT display type (emoji or star)", default="emoji")
    message: str = Field(description="CSAT survey message", default="")
    survey_rules: CSATSurveyRules = Field(description="CSAT survey rules", default_factory=CSATSurveyRules)


class Inbox(BaseModel):
    name: str = Field(description="Name of the inbox")
    greeting_enabled: bool = Field(default=True, description="Whether greeting is enabled")
    greeting_message: str = Field(default="", description="Greeting message for the inbox")
    channel: WebWidgetChannel | EmailChannel | APIChannel | SMSChannel = Field(description="Channel configuration")
    created_at: datetime = Field(description="When the inbox was created")
    updated_at: datetime = Field(description="When the inbox was last updated")
    member_emails: list[str] = Field(description="List of email addresses of inbox members")
    csat_survey_enabled: bool = Field(default=False, description="Whether CSAT survey is enabled")
    csat_config: CSATConfig = Field(description="CSAT configuration", default_factory=CSATConfig)


class InboxList(BaseModel):
    inboxes: list[Inbox] = Field(description="A list of inboxes")


async def generate_inboxes(number_of_inboxes: int):
    """Generate specified number of inboxes using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    inboxes_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing inboxes.json as reference
    reference_inboxes_file = Path(__file__).parent.parent.joinpath("data", "inboxes.json")
    reference_inboxes = []
    try:
        with reference_inboxes_file.open(encoding="utf-8") as f:
            reference_inboxes = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Reference inboxes file not found: {reference_inboxes_file}")

    # Load agents from generated agents.json file for assignment
    agents_file_path = AGENTS_FILE_PATH
    agents_data = []
    try:
        with agents_file_path.open(encoding="utf-8") as f:
            agents_data = json.load(f)
        logger.info(f"Loaded {len(agents_data)} agents for inbox assignment")
    except FileNotFoundError:
        logger.warning(f"Generated agents file not found: {agents_file_path}")
        logger.warning("Inboxes will be generated without predefined member assignments")

    logger.info(f"Generating {number_of_inboxes} inboxes")

    # Generate inboxes using OpenAI with retry logic to ensure we get the requested amount
    all_generated_inboxes = []
    remaining_inboxes = number_of_inboxes
    max_retries = 3

    while remaining_inboxes > 0 and max_retries > 0:
        try:
            logger.start(f"Attempting to generate {remaining_inboxes} more inboxes")

            inboxes_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates realistic inbox data for Chatwoot. Always generate the EXACT number of inboxes requested.",
                    },
                    {
                        "role": "user",
                        "content": f"""Generate EXACTLY {remaining_inboxes} inboxes for a Chatwoot customer support system """
                        f"""of a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {remaining_inboxes} inboxes or more.
                        
                        Learn from these example inboxes to understand the structure and different channel types:
                        ```json
                        {json.dumps(reference_inboxes, indent=2)}
                        ```
                        
                        From the examples, I can see 4 main types of inboxes:
                        
                        1. **Web Widget Inboxes** (Live Chat):
                        - Channel type: "Channel::WebWidget"
                        - Include website_url, widget_color, welcome_title, welcome_tagline
                        - Used for website live chat functionality
                        
                        2. **Email Inboxes**:
                        - Channel type: "Channel::Email"  
                        - Include email, forward_to_email, imap settings if needed
                        - Used for email-based customer support
                        
                        3. **SMS Inboxes**:
                        - Channel type: "Channel::Sms"
                        - Include phone_number and provider configuration
                        - Used for SMS-based customer communication
                        
                        4. **API Inboxes**:
                        - Channel type: "Channel::Api"
                        - Minimal configuration needed
                        - Used for API integrations and custom channels
                        
                        **Distribution Requirements:**
                        - 40% Web Widget inboxes (most common)
                        - 30% Email inboxes  
                        - 20% SMS inboxes
                        - 10% API inboxes
                        
                        **Configuration Guidelines:**
                        - Web widgets: Include realistic website URLs, appealing welcome messages
                        - Email: Use professional email addresses, appropriate forwarding
                        - SMS: Include proper phone numbers with country codes
                        - API: Keep simple with just name and basic config
                        - Make names and descriptions relevant to {settings.DATA_THEME_SUBJECT}
                        - All inboxes should have member_ids populated from available agents
                        
                        **CSAT Configuration:**
                        - About 70% of inboxes should have CSAT surveys enabled (csat_survey_enabled: true)
                        - For enabled CSAT inboxes, include csat_config with:
                          - display_type: either "emoji" or "star" 
                          - message: appropriate CSAT survey message
                          - survey_rules: with operator "contains" and empty values array
                        - Use varied and engaging CSAT messages that match the business context""",
                    },
                ],
                response_format=InboxList,
            )

            batch_inboxes = inboxes_response.choices[0].message.parsed.inboxes

            if batch_inboxes:
                # Add the generated inboxes to our collection
                all_generated_inboxes.extend(batch_inboxes)
                generated_count = len(batch_inboxes)
                remaining_inboxes -= generated_count

                logger.info(f"Generated {generated_count} inboxes in this batch. Total: {len(all_generated_inboxes)}, Remaining: {remaining_inboxes}")

                # If we have enough or more, we're done
                if remaining_inboxes <= 0:
                    break
            else:
                logger.warning("No inboxes generated in this batch")
                max_retries -= 1

        except Exception as e:
            logger.error(f"Error generating inboxes batch: {e}")
            max_retries -= 1

            if max_retries == 0:
                logger.error(f"Failed to generate all requested inboxes. Generated {len(all_generated_inboxes)} out of {number_of_inboxes}")
                if len(all_generated_inboxes) == 0:
                    return
                break

    # Use all generated inboxes, trim to exact number if we got more than requested
    if len(all_generated_inboxes) > number_of_inboxes:
        inboxes_data = all_generated_inboxes[:number_of_inboxes]
        logger.info(f"Trimmed to exactly {number_of_inboxes} inboxes")
    else:
        inboxes_data = all_generated_inboxes

    logger.info(f"Final result: {len(inboxes_data)} inboxes generated successfully")

    # Separate agents and admins from generated data
    agents = [agent for agent in agents_data if agent.get("role") == "agent"]
    admins = [agent for agent in agents_data if agent.get("role") == "administrator"]

    # Add timestamps and member assignments to each inbox
    for inbox in inboxes_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        inbox.created_at = created_at
        inbox.updated_at = updated_at

        # Generate inbox member assignments
        inbox_member_emails = []

        if agents_data:  # Only assign if we have agent data
            # Select random number of agents (25% to 50% of total agents)
            if agents:
                percentage = faker.random_int(min=25, max=50) / 100
                num_agents = max(1, int(len(agents) * percentage))
                selected_agents = faker.random_elements(elements=agents, length=num_agents, unique=True)
                inbox_member_emails.extend([agent["email"] for agent in selected_agents])

            # Randomly select 1-5 admins
            num_admins = faker.random_int(min=1, max=min(5, len(admins))) if admins else 0
            if num_admins > 0:
                selected_admins = faker.random_elements(elements=admins, length=num_admins, unique=True)
                inbox_member_emails.extend([admin["email"] for admin in selected_admins])

        inbox.member_emails = inbox_member_emails

        # Generate CSAT configuration
        # 70% of inboxes will have CSAT enabled
        csat_enabled = faker.boolean(chance_of_getting_true=70)
        inbox.csat_survey_enabled = csat_enabled

        if csat_enabled:
            # Randomly choose between emoji and star display types
            display_type = faker.random_element(["emoji", "star"])

            # Generate appropriate CSAT message based on display type
            if display_type == "emoji":
                csat_message = faker.random_element(
                    [
                        "How was your experience with our support?",
                        "Please rate your satisfaction with our service",
                        "We'd love to hear about your experience!",
                        "How did we do today?",
                        "Rate your support experience",
                    ]
                )
            else:  # star
                csat_message = faker.random_element(
                    [
                        "Please rate your experience with our support team",
                        "How would you rate our service?",
                        "Your feedback helps us improve - please rate us",
                        "Rate your satisfaction on a scale of 1-5 stars",
                        "How many stars would you give our support?",
                    ]
                )

            inbox.csat_config = CSATConfig(display_type=display_type, message=csat_message, survey_rules=CSATSurveyRules(operator="contains", values=[]))

        logger.debug(f"Assigned {len(inbox_member_emails)} members to inbox {inbox.name}, CSAT enabled: {csat_enabled}")

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_inboxes = [inbox.model_dump(mode="json") for inbox in inboxes_data]

    # Store inboxes in JSON file
    with inboxes_file.open("w", encoding="utf-8") as f:
        json.dump(serializable_inboxes, f, indent=2, default=str)
        logger.info(f"Stored {len(inboxes_data)} inboxes with member assignments in {inboxes_file}")


async def seed_inboxes():
    """Seed inboxes from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        inboxes = None
        try:
            with inboxes_file.open(encoding="utf-8") as f:
                inboxes = [Inbox(**inbox) for inbox in json.load(f)]
                logger.info(f"Loaded {len(inboxes)} inboxes from {inboxes_file}")
        except FileNotFoundError:
            logger.error(f"Inboxes file not found: {inboxes_file}")
            logger.error("Please run generate_inboxes() first to create the inboxes file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {inboxes_file}")
            return

        if inboxes is None:
            logger.error("No inboxes loaded from file")
            return

        # Get all users from Chatwoot API to map emails to user IDs
        api_users = await client.list_agents()
        email_to_user = {user["email"]: user for user in api_users}

        logger.info(f"Found {len(api_users)} users in Chatwoot for inbox assignment")

        # Create async tasks for adding inboxes concurrently
        async def add_single_inbox(inbox: Inbox) -> dict | None:
            """Add a single inbox and assign members to it."""
            try:
                # Convert Pydantic model to dict for API call
                inbox_config = inbox.model_dump(exclude={"created_at", "updated_at", "member_emails", "csat_survey_enabled", "csat_config"})

                # Create the inbox
                inbox_data = await client.add_inbox(inbox_config)
                if not inbox_data:
                    logger.error(f"Failed to create inbox {inbox.name}")
                    return None

                logger.info(f"Added inbox {inbox.name}")

                # Use predefined member assignments from JSON
                inbox_member_ids = []
                missing_members = []

                for member_email in inbox.member_emails:
                    if member_email in email_to_user:
                        user = email_to_user[member_email]
                        inbox_member_ids.append(user["id"])
                    else:
                        missing_members.append(member_email)

                if missing_members:
                    logger.warning(f"Inbox {inbox.name}: Could not find users for emails: {missing_members}")

                # Add members to the inbox
                if inbox_member_ids:
                    await client.add_inbox_members(inbox_data["id"], inbox_member_ids)
                    logger.info(f"Added {len(inbox_member_ids)} predefined members to inbox {inbox.name}")
                else:
                    logger.warning(f"No valid members found for inbox {inbox.name}")

                # Update CSAT configuration if enabled
                if inbox.csat_survey_enabled:
                    csat_config = {"csat_survey_enabled": inbox.csat_survey_enabled, "csat_config": inbox.csat_config.model_dump()}

                    updated_inbox = await client.update_inbox(inbox_data["id"], csat_config)
                    if updated_inbox:
                        logger.info(f"Updated CSAT configuration for inbox {inbox.name} (display_type: {inbox.csat_config.display_type})")
                    else:
                        logger.warning(f"Failed to update CSAT configuration for inbox {inbox.name}")

                return inbox_data
            except Exception as e:
                logger.error(f"Error adding inbox {inbox.name}: {e}")
                return None

        # Run all add_inbox calls concurrently
        logger.info(f"Adding {len(inboxes)} inboxes concurrently...")
        results = await asyncio.gather(*[add_single_inbox(inbox) for inbox in inboxes], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added inboxes
        added_inboxes = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.info(f"Successfully added {len(added_inboxes)} out of {len(inboxes)} inboxes with predefined assignments")


async def insert_inboxes():
    """Legacy function - generates inboxes and seeds them into Chatwoot."""
    # For backward compatibility, use the existing inboxes.json file
    reference_inboxes_file = Path(__file__).parent.parent.joinpath("data", "inboxes.json")
    try:
        with reference_inboxes_file.open(encoding="utf-8") as f:
            reference_inboxes = json.load(f)
        await generate_inboxes(len(reference_inboxes))
    except FileNotFoundError:
        logger.warning("Reference inboxes.json not found, generating 15 inboxes")
        await generate_inboxes(15)

    await seed_inboxes()


async def delete_inboxes():
    async with ChatwootClient() as client:
        inboxes = await client.list_inboxes()
        for inbox in inboxes:
            try:
                await client.delete_inbox(inbox["id"])
                logger.info(f"Deleted inbox {inbox['name']}")
            except Exception as e:
                logger.error(f"Error deleting inbox {inbox}: {e}")


async def update_inbox_csat_configs():
    """Update CSAT configurations on all existing inboxes."""
    async with ChatwootClient() as client:
        # Get all existing inboxes
        inboxes = await client.list_inboxes()
        logger.info(f"Found {len(inboxes)} existing inboxes to update with CSAT configuration")

        # Create async tasks for updating CSAT configurations
        async def update_single_inbox_csat(inbox: dict) -> bool:
            """Update CSAT configuration for a single inbox."""
            try:
                # Generate CSAT configuration (70% chance of being enabled)
                csat_enabled = faker.boolean(chance_of_getting_true=70)

                if csat_enabled:
                    # Randomly choose between emoji and star display types
                    display_type = faker.random_element(["emoji", "star"])

                    # Generate appropriate CSAT message based on display type
                    if display_type == "emoji":
                        csat_message = faker.random_element(
                            [
                                "How was your experience with our support?",
                                "Please rate your satisfaction with our service",
                                "We'd love to hear about your experience!",
                                "How did we do today?",
                                "Rate your support experience",
                            ]
                        )
                    else:  # star
                        csat_message = faker.random_element(
                            [
                                "Please rate your experience with our support team",
                                "How would you rate our service?",
                                "Your feedback helps us improve - please rate us",
                                "Rate your satisfaction on a scale of 1-5 stars",
                                "How many stars would you give our support?",
                            ]
                        )

                    csat_config = {
                        "csat_survey_enabled": True,
                        "csat_config": {"display_type": display_type, "message": csat_message, "survey_rules": {"operator": "contains", "values": []}},
                    }
                else:
                    csat_config = {"csat_survey_enabled": False, "csat_config": {"display_type": "emoji", "message": "", "survey_rules": {"operator": "contains", "values": []}}}

                # Update the inbox
                updated_inbox = await client.update_inbox(inbox["id"], csat_config)
                if updated_inbox:
                    status = f"enabled ({csat_config['csat_config']['display_type']})" if csat_enabled else "disabled"
                    logger.info(f"Updated CSAT configuration for inbox '{inbox['name']}': {status}")
                    return True
                else:
                    logger.error(f"Failed to update CSAT configuration for inbox '{inbox['name']}'")
                    return False

            except Exception as e:
                logger.error(f"Error updating CSAT for inbox '{inbox['name']}': {e}")
                return False

        # Run all updates concurrently
        logger.info(f"Updating CSAT configurations for {len(inboxes)} inboxes concurrently...")
        results = await asyncio.gather(*[update_single_inbox_csat(inbox) for inbox in inboxes], return_exceptions=True)

        # Count successful updates
        successful_updates = sum(1 for result in results if result is True)
        logger.info(f"Successfully updated CSAT configurations for {successful_updates} out of {len(inboxes)} inboxes")
