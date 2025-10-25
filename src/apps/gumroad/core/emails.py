import asyncio
import json
import random
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.gumroad.config.settings import settings
from apps.gumroad.core.settings import get_profile_settings
from apps.gumroad.utils.gumroad import GumroadAPI
from common.logger import logger


openai_client = AsyncOpenAI()

# Cache file path using settings.DATA_PATH
EMAILS_CACHE_FILE = settings.DATA_PATH / "generated" / "emails.json"


class Email(BaseModel):
    """Model for broadcast email data"""

    title: str
    message: str = Field(..., description="HTML formatted content for the email")
    files: list[str] = Field(default_factory=list)
    installment_type: Literal["audience", "workflow"] = "audience"
    shown_on_profile: bool = True
    allow_comments: bool = True
    send_emails: bool = False  # Keep as draft by default
    link_id: str | None = None
    published_at: str | None = None
    shown_in_profile_sections: list[str] = Field(default_factory=list)
    paid_more_than_cents: int | None = None
    paid_less_than_cents: int | None = None
    bought_from: str | None = None
    created_after: str = ""
    created_before: str = ""
    bought_products: list[str] | None = None
    bought_variants: list[str] | None = None
    not_bought_products: list[str] = Field(default_factory=list)
    not_bought_variants: list[str] = Field(default_factory=list)
    affiliate_products: list[str] | None = None
    variant_external_id: str | None = None
    send_preview_email: bool = False
    to_be_published_at: str | None = None


class EmailList(BaseModel):
    emails: list[Email]


async def _generate_single_email(email_type: str):
    """Internal function to generate a single email using OpenAI"""
    profile = await get_profile_settings()

    # Add variety to prevent identical content
    styles = [
        "conversational and friendly",
        "professional and authoritative",
        "enthusiastic and energetic",
        "minimalist and direct",
        "storytelling and narrative",
    ]

    email_formats = [
        "HTML with emojis and clear sections",
        "clean and minimalist design",
        "rich formatting with callouts",
        "personal and engaging style",
        "professional newsletter format",
    ]

    chosen_style = random.choice(styles)
    chosen_format = random.choice(email_formats)

    response = await openai_client.beta.chat.completions.parse(
        model="gpt-4.1-mini-2025-04-14",
        messages=[
            {
                "role": "system",
                "content": f"You are an expert in creating engaging email content for a photography business. Write in a {chosen_style} tone using {chosen_format} for the email.",
            },
            {
                "role": "user",
                "content": f"""
                Create a compelling broadcast email for type: "{email_type}"
                
                Seller Profile: {profile}
                
                Requirements:
                • Title: Engaging subject line that drives opens
                • Message: Well-formatted HTML content with:
                  - Clear value proposition
                  - Engaging visuals (using HTML/CSS)
                  - Call to action
                • Consider the email type context:
                  - newsletter: Regular updates and tips
                  - promotion: Special offers and discounts
                  - announcement: New products or features
                  - educational: Photography tips and tutorials
                  - community: User stories and showcases
                
                Make the content unique and specific to a photography business!
                """,
            },
        ],
        response_format=Email,
    )
    return response.choices[0].message.parsed


async def generate_emails(number_of_emails: int) -> dict:
    """
    Generate email data and save to JSON file in settings.DATA_PATH

    Args:
        number_of_emails: Number of emails to generate
    """
    logger.info(f"Generating {number_of_emails} emails...")

    # Distribute emails across different types
    email_types = ["newsletter", "promotion", "announcement", "educational", "community"]
    email_distribution = []

    for i in range(number_of_emails):
        email_type = email_types[i % len(email_types)]
        email_distribution.append(email_type)

    # Generate emails concurrently
    email_tasks = [_generate_single_email(etype) for etype in email_distribution]
    emails = await asyncio.gather(*email_tasks, return_exceptions=True)

    # Process results and handle any exceptions
    emails_data = []
    for i, email in enumerate(emails):
        if isinstance(email, Exception):
            logger.error(f"Error generating email for type '{email_distribution[i]}': {email}")
            continue
        if isinstance(email, Email):
            emails_data.append(email.model_dump())
        else:
            logger.error(f"Unexpected email type for '{email_distribution[i]}': {type(email)}")
            continue

    # Prepare the final data structure
    output_data = {
        "emails": emails_data,
        "count": len(emails_data),
    }

    # Ensure the data directory exists
    EMAILS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Save to JSON file
    with EMAILS_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully generated and saved {len(emails_data)} emails to {EMAILS_CACHE_FILE}")
    return output_data


async def seed_emails() -> dict[str, Any]:
    """
    Insert broadcast emails from generated JSON file into Gumroad

    Creates emails as drafts with:
    - HTML formatted content
    - Audience set to "Everyone"
    - Posted to profile with comments enabled
    - Saved as drafts (not published)

    Returns:
        Dict containing results of email creation
    """
    logger.start("Starting email insertion process...")

    # Load emails from generated JSON file
    if not EMAILS_CACHE_FILE.exists():
        error_msg = f"Emails file not found at {EMAILS_CACHE_FILE}. Run generate_emails() first."
        logger.error(error_msg)
        return {"error": error_msg, "success": False}

    try:
        with EMAILS_CACHE_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
            emails_data = data.get("emails", [])

        if not emails_data:
            error_msg = "No emails found in the JSON file"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}

        logger.info(f"Loaded {len(emails_data)} emails from {EMAILS_CACHE_FILE}")

    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error in emails file: {e!s}"
        logger.error(error_msg)
        return {"error": error_msg, "success": False}

    except Exception as e:
        error_msg = f"Error loading emails file: {e!s}"
        logger.error(error_msg)
        return {"error": error_msg, "success": False}

    # Initialize results tracking
    results = {
        "success": True,
        "total_emails": len(emails_data),
        "created_successfully": [],
        "failed": [],
        "errors": [],
    }

    # Create emails using GumroadAPI
    async with GumroadAPI() as api:
        logger.info("Connected to Gumroad API")

        for i, email_data in enumerate(emails_data, 1):
            try:
                logger.info(f"Creating email {i}/{len(emails_data)}: '{email_data['title']}'")

                # Create the email using the add_email method
                response = await api.add_email(
                    name=email_data["title"],
                    message=email_data["message"],
                    files=email_data.get("files", []),
                    installment_type=email_data.get("installment_type", "audience"),
                    shown_on_profile=email_data.get("shown_on_profile", True),
                    allow_comments=email_data.get("allow_comments", True),
                    send_emails=email_data.get("send_emails", False),  # Keep as draft
                    publish=True,
                    # Optional fields with defaults
                    link_id=email_data.get("link_id"),
                    published_at=email_data.get("published_at"),
                    shown_in_profile_sections=email_data.get("shown_in_profile_sections", []),
                    paid_more_than_cents=email_data.get("paid_more_than_cents"),
                    paid_less_than_cents=email_data.get("paid_less_than_cents"),
                    bought_from=email_data.get("bought_from"),
                    created_after=email_data.get("created_after", ""),
                    created_before=email_data.get("created_before", ""),
                    bought_products=email_data.get("bought_products"),
                    bought_variants=email_data.get("bought_variants"),
                    not_bought_products=email_data.get("not_bought_products", []),
                    not_bought_variants=email_data.get("not_bought_variants", []),
                    affiliate_products=email_data.get("affiliate_products"),
                    variant_external_id=email_data.get("variant_external_id"),
                    send_preview_email=email_data.get("send_preview_email", False),
                    to_be_published_at=email_data.get("to_be_published_at"),
                )

                if response.get("status_code") in [200, 201]:
                    success_info = {
                        "title": email_data["title"],
                        "status": "success",
                        "response": response,
                    }
                    results["created_successfully"].append(success_info)
                    logger.info(f"✅ Successfully created email: '{email_data['title']}'")
                else:
                    error_info = {
                        "title": email_data["title"],
                        "status": "failed",
                        "error": f"API returned status {response.get('status_code')}",
                        "response": response,
                    }
                    results["failed"].append(error_info)
                    results["errors"].append(f"Email '{email_data['title']}': {error_info['error']}")
                    logger.warning(f"⚠️ Failed to create email '{email_data['title']}': {error_info['error']}")

            except Exception as e:
                error_info = {
                    "title": email_data.get("title", f"Email {i}"),
                    "status": "exception",
                    "error": str(e),
                }
                results["failed"].append(error_info)
                results["errors"].append(f"Email '{email_data.get('title', f'Email {i}')}': {e!s}")
                logger.error(f"❌ Exception creating email '{email_data.get('title', f'Email {i}')}': {e!s}")

    # Final results summary
    success_count = len(results["created_successfully"])
    failed_count = len(results["failed"])

    if failed_count > 0:
        results["success"] = False
        logger.warning(f"Email insertion completed with issues: {success_count} successful, {failed_count} failed")
    else:
        logger.info(f"✅ All {success_count} emails created successfully!")

    logger.succeed(f"Email insertion process completed. Summary: {success_count} created, {failed_count} failed")

    return results


# Legacy function for backward compatibility
async def insert_emails() -> dict[str, Any]:
    """
    Legacy function - use generate_emails() and seed_emails() instead
    """
    logger.warning("insert_emails() is deprecated. Use generate_emails() and seed_emails() instead.")

    # Generate emails
    await generate_emails(5)  # Default to 5 emails for backward compatibility

    # Seed emails
    return await seed_emails()
