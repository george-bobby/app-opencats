import json
from pathlib import Path

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.core.users import USERS_CACHE_FILE
from apps.frappehelpdesk.utils.frappe_client import FrappeClient
from common.logger import logger


fake = Faker()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Cache file path
CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "canned_responses.json")


class CannedResponse(BaseModel):
    title: str = Field(description="The title of the canned response")
    message: str = Field(
        description="""The message of the canned response, in HTML format.
        """
    )


class CannedResponseList(BaseModel):
    canned_responses: list[CannedResponse] = Field(description="The canned responses in the list")


async def generate_canned_responses(number_of_canned_responses: int):
    """
    Generate canned responses using GPT and save to JSON file.
    Always generates fresh data and overwrites existing cache.
    Uses data from JSON files instead of querying Frappe client.
    """
    logger.start(f"Generating {number_of_canned_responses} canned responses...")

    # Load users from JSON cache for author assignment
    if not USERS_CACHE_FILE.exists():
        logger.fail("Users cache file not found. Please run generate_users first.")
        return

    try:
        with USERS_CACHE_FILE.open() as f:
            users_cache = json.load(f)
            users_data = users_cache.get("users", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading users cache: {e}")
        return

    if not users_data:
        logger.fail("No users found in cache file")
        return

    # Filter users to only include company domain users
    domain = settings.COMPANY_NAME.lower()
    domain = "".join(c for c in domain if c.isalnum()) + ".com"
    company_users = [user for user in users_data if user.get("email", "").endswith(f"@{domain}")]

    if not company_users:
        logger.fail(f"No company users found for domain {domain}")
        return

    logger.info(f"Generating {number_of_canned_responses} canned responses using {len(company_users)} company users")

    canned_responses = await openai_client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are a helpful assistant that creates canned responses for a helpdesk system.
                Canned responses are pre-written replies that support agents can use to respond to common customer inquiries quickly and consistently.
                """,
            },
            {
                "role": "user",
                "content": f"""Create {number_of_canned_responses} canned responses for a helpdesk system.
                Responses are relevant to corresponding topics/categories such as:
                - General Acknowledgment
                - Escalation
                - Resolution
                - Technical Issues
                - Billing
                - Account Help
                Tone is clear, friendly, and professional
                Placeholder variables like [Customer Name] or [Issue ID] are used where relevant.
                """,
            },
        ],
        response_format=CannedResponseList,
    )
    canned_responses_data = canned_responses.choices[0].message.parsed

    # Add author information to each canned response
    responses_with_authors = []
    for response in canned_responses_data.canned_responses:
        author_user = fake.random_element(company_users)
        response_data = {
            "title": response.title,
            "message": response.message,
            "author": {
                "email": author_user["email"],
                "first_name": author_user["first_name"],
                "last_name": author_user["last_name"],
            },
        }
        responses_with_authors.append(response_data)

    # Save to cache
    try:
        # Ensure the data directory exists
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {"canned_responses": responses_with_authors}

        with CACHE_FILE.open("w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Cached {len(responses_with_authors)} canned responses to {CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving cache: {e}")

    logger.succeed(f"Generated {len(responses_with_authors)} canned responses")


async def seed_canned_responses():
    """
    Read canned responses from cache file and insert them into Frappe.
    """
    logger.start("Seeding canned responses...")

    # Load canned responses from cache
    if not CACHE_FILE.exists():
        logger.fail("Canned responses cache file not found. Please run generate_canned_responses first.")
        return

    try:
        with CACHE_FILE.open() as f:
            cache_data = json.load(f)
            canned_responses_data = cache_data.get("canned_responses", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading canned responses cache: {e}")
        return

    if not canned_responses_data:
        logger.fail("No canned responses found in cache file")
        return

    successful_responses = 0

    # Insert canned responses using cached author information
    for response_data in canned_responses_data:
        try:
            # Use the author information stored in the cache
            author_info = response_data.get("author")
            if author_info and author_info.get("email"):
                author_email = author_info["email"]
            else:
                # Fallback: query for any company user if no author info
                async with FrappeClient() as client:
                    domain = settings.COMPANY_NAME.lower()
                    domain = "".join(c for c in domain if c.isalnum()) + ".com"

                    users = await client.get_list(
                        "User",
                        fields=["name", "email"],
                        filters=[["email", "LIKE", f"%{domain}"]],
                        limit_page_length=settings.LIST_LIMIT,
                    )

                    if not users:
                        logger.warning("No company users found, skipping canned response")
                        continue

                    author_email = fake.random_element(users)["email"]
                    logger.warning(f"No author info in cache for response '{response_data['title']}', using random user: {author_email}")

            async with FrappeClient(username=author_email, password=settings.USER_PASSWORD) as impersonated_client:
                await impersonated_client.insert(
                    {
                        "title": response_data["title"],
                        "message": response_data["message"],
                        "doctype": "HD Canned Response",
                    }
                )

                author_name = f"{author_info.get('first_name', '')} {author_info.get('last_name', '')}" if author_info else author_email
                logger.info(f"Inserted canned response: {response_data['title']} (author: {author_name})")
                successful_responses += 1
        except Exception as e:
            logger.warning(f"Error inserting canned response: {e}")

    logger.succeed(f"Seeded {successful_responses}/{len(canned_responses_data)} canned responses")


async def insert_canned_responses(number_of_canned_responses: int):
    """
    Legacy function for backward compatibility.
    Try to load from cache first, generate if needed, then seed to Frappe.
    """
    # Try to load from cache first
    canned_responses_data = None
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open() as f:
                cache_data = json.load(f)
                cached_responses = cache_data.get("canned_responses", [])
                # Check if we have enough cached responses
                if len(cached_responses) >= number_of_canned_responses:
                    logger.info(f"Loading {number_of_canned_responses} canned responses from cache")
                    # Use only the requested number of responses
                    canned_responses_data = cached_responses[:number_of_canned_responses]
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning(f"Error loading cache, will generate new responses: {e}")
            canned_responses_data = None

    # Generate new responses if not cached or cache is insufficient
    if canned_responses_data is None:
        await generate_canned_responses(number_of_canned_responses)

    # Seed the responses
    await seed_canned_responses()


async def delete_canned_responses():
    async with FrappeClient() as client:
        canned_responses = await client.get_list(
            "HD Canned Response",
            fields=["name"],
            limit_page_length=settings.LIST_LIMIT,
        )
        for canned_response in canned_responses:
            try:
                await client.delete("HD Canned Response", canned_response["name"])
                logger.info(f"Deleted canned response: {canned_response['name']}")
            except Exception as e:
                logger.warning(f"Error deleting canned response: {e}")
