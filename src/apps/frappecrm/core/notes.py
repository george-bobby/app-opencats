import asyncio
import json
from datetime import datetime
from pathlib import Path

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappecrm.config.settings import settings
from apps.frappecrm.utils import frappe_client
from common.logger import logger


fake = Faker()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class Note(BaseModel):
    title: str = Field(description="The title of the note")
    content: str = Field(description="The content of the note, use plain text format, use HTML for formatting.")


async def generate_notes(number_of_notes: int):
    """Generate notes using LLMs and save to JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/notes.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    client = frappe_client.create_client()
    orgs = client.get_list(
        "CRM Organization",
        fields=["name", "industry"],
        limit_page_length=settings.LIST_LIMIT,
    )
    notes = client.get_list(
        "FCRM Note",
        fields=["title"],
        limit_page_length=settings.LIST_LIMIT,
    )
    users = client.get_list(
        "User",
        fields=["name", "email"],
        filters=[["name", "not in", ["Administrator", "Guest"]]],
        limit_page_length=settings.LIST_LIMIT,
    )

    tasks = []

    for _ in range(number_of_notes):
        org = fake.random_element(orgs)

        async def generate_note(org: dict):
            logger.info(f"Generating note for {org['name']}")
            note = await openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a CRM user creating realistic business notes. 
                        Generate professional, human-like notes for a company in the {org["industry"]} industry.
                        Each note should be unique and reflect authentic business interactions.""",
                    },
                    {
                        "role": "user",
                        "content": f"""Create a realistic CRM note for an organization in the {org["industry"]} sector.
                        The note should include:
                        1. A brief, descriptive title
                        2. Detailed content that sounds naturally written by a business professional
                        3. Do not use Markdown formatting, use HTML for formatting

                        Choose one of these scenarios:
                        - Client meeting notes
                        - Internal strategy discussion
                        - Product feedback from customer
                        - Follow-up reminder
                        - Objection handling strategy
                        - Partnership/deal progress update

                        Make it specific, with natural business language, varying tone, and authentic details.
                        Avoid generic content and ensure it reads like something a real person would write in a CRM.

                        Some additional information that can be helpful:
                        - Today is {datetime.now().strftime("%Y-%m-%d")}
                        - We want to create data for {settings.DATA_THEME_SUBJECT}
                        {f"- We already have these notes: {', '.join([note['title'] for note in notes])}" if notes else ""}
                        """,
                    },
                ],
                response_format=Note,
            )

            note = note.choices[0].message.parsed
            return {
                "title": note.title,
                "content": note.content,
                "org_name": org["name"],
                "user_email": fake.random_element(users)["email"],
            }

        tasks.append(generate_note(org))

    notes_data = await asyncio.gather(*tasks)

    # Save the generated notes to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(notes_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(notes_data)} notes to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving notes to file: {e}")


async def insert_notes(number_of_notes: int):
    """Insert notes from JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/notes.json")

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Notes data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            notes_data = json.load(f)
        logger.info(f"Loaded {len(notes_data)} notes from file")
    except Exception as e:
        logger.error(f"Error reading notes from file: {e}")
        return

    client = frappe_client.create_client()
    users = client.get_list(
        "User",
        fields=["name", "email"],
        filters=[["name", "not in", ["Administrator", "Guest"]]],
        limit_page_length=settings.LIST_LIMIT,
    )

    # Process notes concurrently with a semaphore to limit to 8 at once
    semaphore = asyncio.Semaphore(8)

    async def insert_note(note_data):
        async with semaphore:
            try:
                # Use run_in_executor to make the blocking client.insert call non-blocking
                loop = asyncio.get_event_loop()
                try:
                    # Find user by email
                    user = next((u for u in users if u["email"] == note_data["user_email"]), None)
                    if not user:
                        user = fake.random_element(users)

                    impersonated_client = frappe_client.create_client(
                        username=user["name"],
                        password=settings.USER_PASSWORD,
                    )
                    logger.info(f"Created impersonated client for {user['name']}")
                except Exception as e:
                    logger.error(f"Error creating impersonated client: {e}")
                    return

                await loop.run_in_executor(
                    None,
                    lambda: impersonated_client.insert(
                        {
                            "doctype": "FCRM Note",
                            "title": note_data["title"],
                            "content": note_data["content"],
                        }
                    ),
                )
                logger.info(f"Inserted note: {note_data['title']}")
            except Exception as e:
                logger.error(f"Error inserting note: {e}")

    # Run note insertions for the requested number
    await asyncio.gather(*[insert_note(note_data) for note_data in notes_data[:number_of_notes]])


async def delete_notes():
    client = frappe_client.create_client()
    notes = client.get_list(
        "FCRM Note",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for note in notes:
        try:
            client.delete("FCRM Note", note["name"])
            logger.info(f"Deleted note: {note['name']}")
        except Exception as e:
            logger.error(f"Error deleting note: {e}")
