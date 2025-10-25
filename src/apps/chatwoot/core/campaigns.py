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
CAMPAIGN_DATA_FILE_PATH = settings.DATA_PATH / "generated" / "campaigns.json"


class TriggerRules(BaseModel):
    url: str = Field(description="URL pattern to trigger the campaign")
    time_on_page: int = Field(description="Time in seconds before triggering the campaign")


class Audience(BaseModel):
    id: int = Field(description="The ID of the audience (label)")  # noqa: A003, RUF100
    type: str = Field(description="The type of audience", default="Label")  # noqa: A003, RUF100


class Campaign(BaseModel):
    title: str = Field(description="The title of the campaign")
    message: str = Field(description="The message content of the campaign")
    enabled: bool = Field(description="Whether the campaign is enabled", default=True)
    trigger_only_during_business_hours: bool = Field(description="Whether to trigger only during business hours", default=False)
    trigger_rules: TriggerRules | None = Field(description="Rules for triggering the campaign (live chat only)", default=None)
    scheduled_at: str | None = Field(description="Scheduled time for SMS campaigns (ISO format)", default=None)
    audience: list[Audience] | None = Field(description="Audience for SMS campaigns", default=None)
    created_at: datetime = Field(description="When the campaign was created")
    updated_at: datetime = Field(description="When the campaign was last updated")


class CampaignList(BaseModel):
    campaigns: list[Campaign] = Field(description="A list of campaigns")


async def generate_campaigns(number_of_campaigns: int):
    """Generate specified number of campaigns using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    CAMPAIGN_DATA_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger.start(f"Generating {number_of_campaigns} campaigns")

    # Generate campaigns using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            campaigns_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates realistic campaign data for Chatwoot. Always generate the EXACT number of campaigns requested.",
                    },
                    {
                        "role": "user",
                        "content": f"""Generate EXACTLY {number_of_campaigns} campaigns for a Chatwoot customer support system of {settings.COMPANY_NAME}, a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {number_of_campaigns} campaigns, no more, no less.
                        
                        Create diverse, engaging campaigns for customer engagement. Include a mix of:
                        
                        **Live Chat Campaigns (70% of campaigns):**
                        - Trigger on specific pages (pricing, contact, checkout, product pages, etc.)
                        - Include trigger_rules with:
                          - Full URLs (https://example.com/pricing, https://example.com/contact, etc.)
                          - Time on page between 10-60 seconds
                        - Set trigger_only_during_business_hours to true or false

                        **Email Campaigns (30% of campaigns):**
                        - Welcome sequences, follow-ups, newsletters
                        - No trigger_rules needed for email campaigns
                        - Focus on customer onboarding and retention

                        Each campaign should be unique and tailored to {settings.COMPANY_NAME} ({settings.DATA_THEME_SUBJECT}).""",
                    },
                ],
                response_format=CampaignList,
            )

            campaigns_data = campaigns_response.choices[0].message.parsed.campaigns

            # Validate we got the correct number
            if len(campaigns_data) >= number_of_campaigns:
                # Trim to exact number if we got more
                campaigns_data = campaigns_data[:number_of_campaigns]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(campaigns_data)} campaigns, need {number_of_campaigns}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_campaigns} campaigns after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate campaigns after {max_retries} attempts")
                return

    # Add timestamps to each campaign
    for campaign in campaigns_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        campaign.created_at = created_at
        campaign.updated_at = updated_at

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_campaigns = [campaign.model_dump(mode="json") for campaign in campaigns_data]

    # Store campaigns in JSON file
    with CAMPAIGN_DATA_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable_campaigns, f, indent=2, default=str)
        logger.succeed(f"Stored {len(campaigns_data)} campaigns in {CAMPAIGN_DATA_FILE_PATH}")


async def seed_campaigns():
    """Seed campaigns from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        campaigns = None
        try:
            with CAMPAIGN_DATA_FILE_PATH.open(encoding="utf-8") as f:
                campaigns = [Campaign(**campaign) for campaign in json.load(f)]
                logger.info(f"Loaded {len(campaigns)} campaigns from {CAMPAIGN_DATA_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Campaigns file not found: {CAMPAIGN_DATA_FILE_PATH}")
            logger.error("Please run generate_campaigns() first to create the campaigns file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {CAMPAIGN_DATA_FILE_PATH}")
            return

        if campaigns is None:
            logger.error("No campaigns loaded from file")
            return

        # Get and validate resources
        inboxes = await client.list_inboxes()
        agents = await client.list_agents()
        labels = await client.list_labels()

        if not await validate_campaign_resources(inboxes, agents):
            return

        # Prepare resources
        _, live_chat_inboxes, sms_inboxes = prepare_campaign_resources(inboxes)

        # Create async tasks for adding campaigns concurrently
        async def add_single_campaign(campaign: Campaign) -> dict | None:
            """Add a single campaign and return the campaign if successful, None if failed."""
            try:
                await process_single_campaign(campaign, live_chat_inboxes, sms_inboxes, agents, labels, client)
                return campaign.model_dump()
            except Exception as e:
                logger.error(f"Error adding campaign {campaign.title}: {e}")
                return None

        # Run all add_campaign calls concurrently
        logger.start(f"Adding {len(campaigns)} campaigns concurrently...")
        results = await asyncio.gather(*[add_single_campaign(campaign) for campaign in campaigns], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added campaigns
        added_campaigns = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.succeed(f"Successfully added {len(added_campaigns)} out of {len(campaigns)} campaigns")


def prepare_campaign_resources(
    inboxes: list,
    # agents: list, labels: list
) -> tuple[str, list, list]:
    """Prepare and categorize resources for campaign creation."""
    # Find live chat and SMS inboxes
    live_chat_inboxes = [inbox for inbox in inboxes if inbox.get("channel_type") == "Channel::WebWidget"]
    sms_inboxes = [inbox for inbox in inboxes if inbox.get("channel_type") == "Channel::Sms"]

    # Determine campaign type based on available inboxes
    campaign_type = "live_chat" if live_chat_inboxes else "sms" if sms_inboxes else "live_chat"

    return campaign_type, live_chat_inboxes, sms_inboxes


def create_live_chat_campaign_data(campaign: Campaign, inbox_id: int, sender_id: int) -> dict:
    """Create campaign data for live chat campaigns."""
    # Handle case where trigger_rules is None (for default live chat campaigns)
    if campaign.trigger_rules is None:
        # Provide default trigger rules for campaigns without them
        trigger_rules = {"url": "https://example.com/", "time_on_page": 30}
    else:
        # Ensure URL is a full URL, not a relative path
        trigger_rules = campaign.trigger_rules.model_dump()
        if not trigger_rules["url"].startswith(("http://", "https://")):
            # Convert relative URL to full URL
            if trigger_rules["url"].startswith("/"):
                trigger_rules["url"] = f"https://example.com{trigger_rules['url']}"
            else:
                trigger_rules["url"] = f"https://example.com/{trigger_rules['url']}"

    return {
        "title": campaign.title,
        "message": campaign.message,
        "inbox_id": inbox_id,
        "sender_id": sender_id,
        "enabled": campaign.enabled,
        "trigger_only_during_business_hours": campaign.trigger_only_during_business_hours,
        "trigger_rules": trigger_rules,
    }


def create_sms_campaign_data(campaign: Campaign, inbox_id: int, labels: list) -> dict:
    """Create campaign data for SMS campaigns."""
    if not campaign.scheduled_at or not campaign.audience:
        # Generate default values for SMS campaign
        from datetime import datetime, timedelta

        scheduled_at = (datetime.now() + timedelta(hours=1)).isoformat() + "Z"
        audience = [{"id": faker.random_element(labels)["id"], "type": "Label"}] if labels else []
    else:
        scheduled_at = campaign.scheduled_at
        # Map placeholder IDs to actual label IDs if needed
        audience = []
        for aud in campaign.audience:
            if labels:
                # Use actual label ID instead of placeholder
                actual_label = faker.random_element(labels)
                audience.append({"id": actual_label["id"], "type": "Label"})
            else:
                audience.append(aud.model_dump())

    return {
        "title": campaign.title,
        "message": campaign.message,
        "inbox_id": inbox_id,
        "scheduled_at": scheduled_at,
        "audience": audience,
    }


async def validate_campaign_resources(inboxes: list, agents: list) -> bool:
    """Validate that required resources exist for campaign creation."""
    if not inboxes:
        logger.error("No inboxes found. Cannot create campaigns without inboxes.")
        return False
    if not agents:
        logger.error("No agents found. Cannot create campaigns without agents.")
        return False
    return True


async def process_single_campaign(
    campaign: Campaign,
    live_chat_inboxes: list,
    sms_inboxes: list,
    agents: list,
    labels: list,
    client: ChatwootClient,
) -> None:
    """Process a single campaign and add it to Chatwoot."""
    # Determine campaign type and create data
    if campaign.trigger_rules and not campaign.scheduled_at:
        # Live chat campaign
        if not live_chat_inboxes:
            logger.warning(f"Skipping live chat campaign {campaign.title}: No live chat inboxes available")
            return
        sender_id = faker.random_element(agents)["id"]
        inbox_id = faker.random_element(live_chat_inboxes)["id"]
        campaign_data = create_live_chat_campaign_data(campaign, inbox_id, sender_id)
        campaign_type = "live_chat"
    elif campaign.scheduled_at or campaign.audience:
        # SMS campaign
        if not sms_inboxes:
            logger.warning(f"Skipping SMS campaign {campaign.title}: No SMS inboxes available")
            return
        inbox_id = faker.random_element(sms_inboxes)["id"]
        campaign_data = create_sms_campaign_data(campaign, inbox_id, labels)
        campaign_type = "sms"
    else:
        # Default to live chat
        if not live_chat_inboxes:
            logger.warning(f"Skipping unclear campaign {campaign.title}: No live chat inboxes available")
            return
        sender_id = faker.random_element(agents)["id"]
        inbox_id = faker.random_element(live_chat_inboxes)["id"]
        campaign_data = create_live_chat_campaign_data(campaign, inbox_id, sender_id)
        campaign_type = "live_chat"

    await client.add_campaign(campaign_data)
    logger.info(f"Added {campaign_type} campaign: {campaign.title}")


async def insert_campaigns(number_of_campaigns: int):
    """Legacy function - generates campaigns and seeds them into Chatwoot."""
    await generate_campaigns(number_of_campaigns)
    await seed_campaigns()


async def delete_campaigns():
    async with ChatwootClient() as client:
        campaigns = await client.list_campaigns()

        for campaign in campaigns:
            await client.delete_campaign(campaign["id"])
            logger.info(f"Deleted campaign: {campaign['title']}")
