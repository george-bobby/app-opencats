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
CANNED_RESPONSE_FILE_PATH = settings.DATA_PATH / "generated" / "canned_responses.json"


class CannedResponse(BaseModel):
    short_code: str = Field(description="The short code for the canned response, in snake_case")
    content: str = Field(description="The content of the canned response")
    created_at: datetime = Field(description="When the canned response was created")
    updated_at: datetime = Field(description="When the canned response was last updated")


class CannedResponseList(BaseModel):
    canned_responses: list[CannedResponse] = Field(description="A list of canned responses")


async def generate_canned_responses(number_of_canned_responses: int):
    """Generate specified number of canned responses using OpenAI and save them to JSON file."""
    # Ensure the generated directory exists
    CANNED_RESPONSE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger.start(f"Generating {number_of_canned_responses} canned responses")

    # Generate canned responses using OpenAI with retry logic to ensure we get the requested amount
    max_retries = 3
    for attempt in range(max_retries):
        try:
            canned_responses_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates realistic canned response data for Chatwoot. Always generate the EXACT number of canned responses requested."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Generate EXACTLY {number_of_canned_responses} canned responses for a Chatwoot customer support system of {settings.COMPANY_NAME}, a {settings.DATA_THEME_SUBJECT}.

                        IMPORTANT: You must generate exactly {number_of_canned_responses} canned responses, no more, no less.
                        
                        Create diverse, professional canned responses that customer support agents would commonly use. Include:
                        
                        **Greeting & Welcome Responses:**
                        - welcome_new_customer, first_contact_greeting, thank_you_for_contacting
                        - welcome_back, returning_customer_greeting
                        
                        **Common Support Responses:**
                        - troubleshooting_started, checking_account, investigating_issue
                        - escalation_notice, follow_up_scheduled, issue_resolved
                        
                        **Closing & Follow-up Responses:**
                        - conversation_closing, satisfaction_check, additional_help
                        - feedback_request, case_closed, follow_up_reminder
                        
                        **Specific Situation Responses:**
                        - technical_difficulties, billing_inquiry, feature_request
                        - refund_process, account_setup, password_reset
                        
                        Each response should:
                        - Have a short, descriptive short_code (snake_case, 2-4 words)
                        - Include professional, helpful content
                        - Be relevant to {settings.COMPANY_NAME} ({settings.DATA_THEME_SUBJECT}) context
                        - Use placeholders like {{contact.name}} when appropriate
                        - Be concise but complete (1-3 sentences typically)""",
                    },
                ],
                response_format=CannedResponseList,
            )

            canned_responses_data = canned_responses_response.choices[0].message.parsed.canned_responses

            # Validate we got the correct number
            if len(canned_responses_data) >= number_of_canned_responses:
                # Trim to exact number if we got more
                canned_responses_data = canned_responses_data[:number_of_canned_responses]
                break
            else:
                logger.warning(f"Attempt {attempt + 1}: Generated {len(canned_responses_data)} canned responses, need {number_of_canned_responses}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate {number_of_canned_responses} canned responses after {max_retries} attempts")
                    return

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate canned responses after {max_retries} attempts")
                return

    # Add timestamps to each canned response
    for response in canned_responses_data:
        # Generate faker timestamps
        created_at = faker.date_time_between(start_date="-1y", end_date="-1m")
        updated_at = faker.date_time_between(start_date=created_at, end_date="now")
        response.created_at = created_at
        response.updated_at = updated_at

    # Convert Pydantic models to dictionaries before serializing to JSON
    serializable_responses = [response.model_dump(mode="json") for response in canned_responses_data]

    # Store canned responses in JSON file
    with CANNED_RESPONSE_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(serializable_responses, f, indent=2, default=str)
        logger.succeed(f"Stored {len(canned_responses_data)} canned responses in {CANNED_RESPONSE_FILE_PATH}")


async def seed_canned_responses():
    """Seed canned responses from JSON file into Chatwoot."""
    async with ChatwootClient() as client:
        canned_responses = None
        try:
            with CANNED_RESPONSE_FILE_PATH.open(encoding="utf-8") as f:
                canned_responses = [CannedResponse(**response) for response in json.load(f)]
                logger.info(f"Loaded {len(canned_responses)} canned responses from {CANNED_RESPONSE_FILE_PATH}")
        except FileNotFoundError:
            logger.error(f"Canned responses file not found: {CANNED_RESPONSE_FILE_PATH}")
            logger.error("Please run generate_canned_responses() first to create the canned responses file")
            return
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in {CANNED_RESPONSE_FILE_PATH}")
            return

        if canned_responses is None:
            logger.error("No canned responses loaded from file")
            return

        # Create async tasks for adding canned responses concurrently
        async def add_single_canned_response(response: CannedResponse) -> dict | None:
            """Add a single canned response and return the response if successful, None if failed."""
            try:
                await client.add_canned_response(response.short_code, response.content)
                return response.model_dump()
            except Exception as e:
                logger.error(f"Error adding canned response {response.short_code}: {e}")
                return None

        # Run all add_canned_response calls concurrently
        logger.start(f"Adding {len(canned_responses)} canned responses concurrently...")
        results = await asyncio.gather(*[add_single_canned_response(response) for response in canned_responses], return_exceptions=True)

        # Filter out None results and exceptions to get successfully added responses
        added_responses = [result for result in results if result is not None and not isinstance(result, Exception)]

        logger.succeed(f"Successfully added {len(added_responses)} out of {len(canned_responses)} canned responses")


async def insert_canned_responses(number_of_canned_responses: int):
    """Legacy function - generates canned responses and seeds them into Chatwoot."""
    await generate_canned_responses(number_of_canned_responses)
    await seed_canned_responses()


async def delete_canned_responses():
    async with ChatwootClient() as client:
        canned_responses = await client.list_canned_responses()
        for canned_response in canned_responses:
            await client.delete_canned_response(canned_response["id"])
            logger.info(f"Deleted canned response: {canned_response['short_code']}")
