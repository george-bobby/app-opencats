import asyncio
import json
from pathlib import Path
from typing import Literal

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappecrm.config.settings import settings
from apps.frappecrm.utils import frappe_client
from common.logger import logger


fake = Faker()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class EmailTemplate(BaseModel):
    name: str = Field(description="The name of the email template, should be unique and specific")
    subject: str = Field(description="The subject of the email template")
    response: str = Field(description="The body of the email template, in HTML format")
    doctype: Literal["CRM Lead", "CRM Deal"]


class Email(BaseModel):
    subject: str = Field(description="The subject of the email")
    body: str = Field(description="The body of the email, in HTML format")
    sent_or_received: Literal["Sent", "Received"] = Field(description="Whether the email was sent or received")


class EmailConversation(BaseModel):
    emails: list[Email] = Field(description="The emails in the conversation")


async def generate_email_templates(number_of_templates: int, template_type: str = "random"):
    """Generate email templates using LLMs and save to JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/email_templates.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Generating new email templates with GPT")
    email_templates_data = await generate_email_templates_with_gpt(number_of_templates, template_type)

    # Save the generated templates to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(email_templates_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(email_templates_data)} email templates to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving email templates to file: {e}")


async def insert_email_templates(
    number_of_templates: int,  # template_type: str = "random"
):
    client = frappe_client.create_client()
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/email_templates.json")

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Email templates data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            email_templates_data = json.load(f)
        logger.info(f"Loaded {len(email_templates_data)} email templates from file")
    except Exception as e:
        logger.error(f"Error reading email templates from file: {e}")
        return

    logger.start(f"Inserting {len(email_templates_data)} email templates")

    # Insert templates from the data
    existing_templates = client.get_list(
        "Email Template",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_template_names = [template["name"] for template in existing_templates]

    inserted_count = 0
    for template_data in email_templates_data[:number_of_templates]:
        # Skip if template already exists
        if template_data["name"] in existing_template_names:
            logger.info(f"Template '{template_data['name']}' already exists, skipping")
            continue

        try:
            client.insert(
                {
                    "doctype": "Email Template",
                    "subject": template_data["subject"],
                    "response": template_data["response"],
                    "response_html": "",
                    "name": template_data["name"],
                    "enabled": 1,
                    "use_html": False,
                    "owner": "",
                    "reference_doctype": template_data["doctype"],
                    "content_type": "Rich Text",
                }
            )
            inserted_count += 1
        except Exception as e:
            logger.warning(f"Error inserting email template '{template_data['name']}': {e}")

    logger.succeed(f"Successfully inserted {inserted_count} email templates")


async def generate_email_templates_with_gpt(number_of_templates: int, template_type: str = "random"):
    """Generate email templates using GPT and return them as a list of dictionaries"""
    template_types = {
        "welcome": {"name": "Welcome Email", "doctype": "CRM Lead"},
        "follow_up": {"name": "Follow-up Email", "doctype": "CRM Lead"},
        "deal_closure": {"name": "Deal Closure", "doctype": "CRM Deal"},
        "intro_pitch": {"name": "Introductory Pitch", "doctype": "CRM Lead"},
        "meeting_reminder": {"name": "Meeting Reminder", "doctype": "CRM Deal"},
        "random": {"name": "Random", "doctype": ""},
    }

    client = frappe_client.create_client()

    existing_templates = client.get_list(
        "Email Template",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_template_names = [template["name"] for template in existing_templates]

    template_tasks = []

    for _ in range(number_of_templates):

        async def generate_email_template():
            template_info = None
            template_info = fake.random_element(elements=list(template_types.values())) if template_type == "random" else template_types.get(template_type, template_types["random"])

            prompt_content = f"Generate an email template for {template_info['name']}"

            doctype_instruction = f" The doctype should be {template_info['doctype']}." if template_info["doctype"] else ""
            logger.info(f"Generating {template_info['name']} template...")
            template_response = await openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a helpful assistant that generates realistic looking email templates for a CRM system. 
                        The templates should be professional, engaging, and follow best practices for email communication.
                        We are using the CRM system of a company focusing on {settings.DATA_THEME_SUBJECT}.""",
                    },
                    {
                        "role": "user",
                        "content": f"""{prompt_content}.{doctype_instruction} 
                        Include a compelling subject line and HTML-formatted body with placeholders for personalization like {{{{first_name}}}}, {{{{company}}}}, etc. where appropriate.
                        Dont use the same template name as any of the following: {", ".join(existing_template_names)}""",
                    },
                ],
                response_format=EmailTemplate,
            )

            template = template_response.choices[0].message.parsed
            return {
                "name": template.name,
                "subject": template.subject,
                "response": template.response,
                "doctype": template.doctype,
            }

        template_tasks.append(generate_email_template())

    # Run all tasks concurrently and gather results
    email_templates_data = await asyncio.gather(*template_tasks)
    return email_templates_data
