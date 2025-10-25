import asyncio
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappecrm.config.settings import settings
from apps.frappecrm.core.emails import Email
from apps.frappecrm.core.notes import Note
from apps.frappecrm.utils import frappe_client
from common.logger import logger


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
fake = Faker()


async def generate_leads(number_of_leads: int):
    """Generate leads data and save to JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/leads.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Generating new leads data")
    leads_data = await generate_leads_data(number_of_leads)

    # Save the generated leads to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(leads_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(leads_data)} leads to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving leads to file: {e}")


async def insert_leads(number_of_leads: int):
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/leads.json")
    client = frappe_client.create_client()

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Leads data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            leads_data = json.load(f)
        logger.info(f"Loaded {len(leads_data)} leads from file")
    except Exception as e:
        logger.error(f"Error reading leads from file: {e}")
        return

    # Deduplicate leads data by email before processing
    seen_emails = set()
    deduplicated_leads = []
    for lead in leads_data:
        if lead["email"] not in seen_emails:
            seen_emails.add(lead["email"])
            deduplicated_leads.append(lead)

    logger.info(f"Deduplicated {len(leads_data)} leads to {len(deduplicated_leads)} unique leads by email")

    leads_to_process = deduplicated_leads[:number_of_leads]

    logger.start(f"Inserting {len(leads_to_process)} leads, skipping existing")

    # Get existing leads to avoid duplicates with database
    existing_leads = client.get_list(
        "CRM Lead",
        fields=["email"],
        limit_page_length=settings.LIST_LIMIT,
    )
    existing_emails = {lead["email"] for lead in existing_leads}

    leads_to_insert = []
    for lead_data in leads_to_process:
        # Skip if lead already exists in database
        if lead_data["email"] in existing_emails:
            logger.info(f"Lead '{lead_data['first_name']} {lead_data['last_name']} - {lead_data['email']}' already exists, skipping")
            continue

        # Remove lead_owner field to avoid link validation errors
        lead_data.pop("lead_owner", None)

        leads_to_insert.append(lead_data)

    if not leads_to_insert:
        logger.info("No new leads to insert")
        return

    # Create a semaphore to limit concurrent executions to 1 (avoid deadlocks)
    semaphore = asyncio.Semaphore(1)

    async def insert_lead(lead):
        async with semaphore:
            try:
                # Use run_in_executor to make the blocking client.insert call non-blocking
                loop = asyncio.get_event_loop()
                # Use admin client instead of impersonating users
                await loop.run_in_executor(None, lambda: client.insert(lead))
            except Exception as e:
                logger.error(e)

    await asyncio.gather(*[insert_lead(lead) for lead in leads_to_insert])
    logger.succeed(f"Successfully inserted {len(leads_to_insert)} leads")


async def generate_leads_data(number_of_leads: int):
    """Generate leads data and return them as a list of dictionaries"""
    client = frappe_client.create_client()

    users = client.get_list(
        "User",
        fields=["name", "email"],
        filters=[["name", "not in", ["Administrator", "Guest"]]],
        limit_page_length=settings.LIST_LIMIT,
    )
    orgs = client.get_list(
        "CRM Organization",
        fields=["name", "industry", "website", "no_of_employees", "annual_revenue"],
        limit_page_length=settings.LIST_LIMIT,
    )
    contacts = client.get_list(
        "Contact",
        fields=[
            "first_name",
            "last_name",
            "email_id",
            "phone",
            "gender",
            "designation",
            "company_name",
            "salutation",
        ],
        limit_page_length=settings.LIST_LIMIT,
    )
    leads = []
    for _ in range(number_of_leads):
        current_user = fake.random_element(users)
        contact = fake.random_element(contacts)
        org = next((o for o in orgs if o["name"] == contact["company_name"]), None)

        if not org:
            continue

        lead = {
            "doctype": "CRM Lead",
            "salutation": contact["salutation"],
            "first_name": contact["first_name"],
            "last_name": contact["last_name"],
            "email": contact["email_id"],
            "mobile_no": contact["phone"],
            "gender": contact["gender"],
            "job_title": contact["designation"],
            "organization": contact["company_name"],
            "website": org["website"] if org else "",
            "no_of_employees": org["no_of_employees"] if org else "",
            "territory": "",
            "annual_revenue": org["annual_revenue"] if org else "",
            "industry": org["industry"] if org else "",
            "status": fake.random_element(
                OrderedDict(
                    [
                        ("New", 0.2),
                        ("Contacted", 0.3),
                        ("Qualified", 0.2),
                        ("Nurture", 0.1),
                        ("Unqualified", 0.1),
                        ("Junk", 0.1),
                    ]
                )
            ),
            "lead_owner": current_user["name"],
            "source": fake.random_element(
                [
                    "Advertisement",
                    "Campaign",
                    "Cold Calling",
                    "Customer's Vendor",
                    "Exhibition",
                    "Existing Customer",
                    "Mass Mailing",
                    "Reference",
                    "Supplier Reference",
                    "Walk In",
                ]
            ),
        }
        leads.append(lead)

    return leads


async def convert_to_deals(number_of_deals: int):
    client = frappe_client.create_client()

    leads = client.get_list(
        "CRM Lead",
        fields=["name", "first_name", "last_name", "organization", "lead_owner"],
        limit_page_length=settings.LIST_LIMIT,
    )
    number_of_deals = len(leads) if number_of_deals > len(leads) else number_of_deals
    leads = fake.random_elements(elements=leads, length=number_of_deals)
    logger.start(f"Converting {len(leads)} leads to deals")
    for lead in leads:
        try:
            # Use admin client instead of impersonation
            client.post_api(
                "crm.fcrm.doctype.crm_lead.crm_lead.convert_to_deal",
                {
                    "lead": lead["name"],
                    "organization": lead["organization"],
                },
            )
            # Add small delay to prevent server overload
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(e)

    logger.succeed(f"Successfully converted {len(leads)} leads to deals")


async def add_calls(number_of_leads: int, calls_per_lead: tuple[int, int]):
    client = frappe_client.create_client()

    leads = client.get_list(
        "CRM Lead",
        fields=[
            "name",
            "first_name",
            "last_name",
            "organization",
            "lead_owner",
            "mobile_no",
            "owner",
        ],
        limit_page_length=settings.LIST_LIMIT,
    )
    number_of_leads = len(leads) if number_of_leads > len(leads) else number_of_leads
    leads = fake.random_elements(elements=leads, length=number_of_leads, unique=True)
    logger.start(f"Adding calls to {len(leads)} leads")

    for lead in leads:
        for _ in range(fake.random_int(calls_per_lead[0], calls_per_lead[1])):
            try:
                call_direction = fake.random_element(["Incoming", "Outgoing"])
                our_number = "(123) 456-7890"
                their_number = lead["mobile_no"] if lead["mobile_no"] else "(098) 765-4321"

                call_log = {
                    "id": fake.bothify(text="??????"),
                    "doctype": "CRM Call Log",
                    "telephony_medium": "Manual",
                    "reference_doctype": "CRM Lead",
                    "reference_docname": lead["name"],
                    "duration": fake.random_int(30, 360),
                    "type": call_direction,
                    "to": their_number if call_direction == "Outgoing" else our_number,
                    "from": our_number if call_direction == "Outgoing" else their_number,
                    "status": fake.random_element(
                        OrderedDict(
                            [
                                ("Initiated", 0.05),
                                ("Completed", 0.7),
                                ("Failed", 0.05),
                                ("Busy", 0.05),
                                ("No Answer", 0.05),
                                ("Queued", 0.05),
                                ("Canceled", 0.05),
                            ]
                        )
                    ),
                    "caller": lead["owner"] if call_direction == "Outgoing" else None,
                    "receiver": lead["owner"] if call_direction == "Incoming" else None,
                }
                # logger.info(json.dumps(call_log, indent=4))
                client.insert(call_log)
            except Exception as e:
                logger.error(e)
                raise

    logger.succeed(f"Successfully inserted {len(leads)} calls")


class Task(BaseModel):
    title: str = Field(description="The title of the task")
    description: str = Field(description="The description of the task")


class Comment(BaseModel):
    content: str = Field(description="Comment from the team about this lead or deal")


class LeadContent(BaseModel):
    emails: list[Email] = Field(description="The emails in the conversation")
    notes: list[Note] = Field(description="The notes for this lead")
    tasks: list[Task] = Field(description="The tasks for this lead")
    comments: list[Comment] = Field(description="The comments for this lead")


async def generate_content(
    number_of_leads: int,
    emails_per_lead: tuple[int, int],
    notes_per_lead: tuple[int, int],
    tasks_per_lead: tuple[int, int],
    comments_per_lead: tuple[int, int],
):
    """Generate lead content data using LLMs and save to JSON file"""
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/lead_content.json")

    # Ensure the directory exists
    json_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.start("Generating new lead content with GPT")
    lead_content_data = await generate_lead_content_data(
        number_of_leads,
        emails_per_lead,
        notes_per_lead,
        tasks_per_lead,
        comments_per_lead,
    )

    # Save the generated content to the JSON file
    try:
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(lead_content_data, f, indent=2, ensure_ascii=False)
        logger.succeed(f"Saved content for {len(lead_content_data)} leads to {json_file_path}")
    except Exception as e:
        logger.error(f"Error saving lead content to file: {e}")


async def add_content(
    number_of_leads: int,
    # emails_per_lead: tuple[int, int],
    # notes_per_lead: tuple[int, int],
    # tasks_per_lead: tuple[int, int],
    # comments_per_lead: tuple[int, int],
):
    # Define the path to the JSON file
    json_file_path = Path(__file__).parent.parent.joinpath("data/generated/lead_content.json")

    # Check if the JSON file exists and read from it
    if not json_file_path.exists():
        logger.error(f"Lead content data file not found at {json_file_path}. Please run generate command first.")
        return

    try:
        with json_file_path.open(encoding="utf-8") as f:
            lead_content_data = json.load(f)
        logger.info(f"Loaded content for {len(lead_content_data)} leads from file")
    except Exception as e:
        logger.error(f"Error reading lead content from file: {e}")
        return

    logger.start(f"Inserting content for {min(len(lead_content_data), number_of_leads)} leads")

    # Insert content from the data
    await insert_lead_content_from_data(lead_content_data[:number_of_leads])
    logger.succeed(f"Successfully inserted content for {min(len(lead_content_data), number_of_leads)} leads")


async def generate_lead_content_data(
    number_of_leads: int,
    emails_per_lead: tuple[int, int],
    notes_per_lead: tuple[int, int],
    tasks_per_lead: tuple[int, int],
    comments_per_lead: tuple[int, int],
):
    """Generate lead content data using GPT and return as a list of dictionaries"""

    # Read leads from the generated JSON file instead of API during generation
    leads_json_path = Path(__file__).parent.parent.joinpath("data/generated/leads.json")
    users_json_path = Path(__file__).parent.parent.joinpath("data/generated/users.json")

    if not leads_json_path.exists():
        logger.error("No leads.json file found. Please generate leads first.")
        return []

    if not users_json_path.exists():
        logger.error("No users.json file found. Please generate users first.")
        return []

    # Load leads and users from JSON files
    with leads_json_path.open("r", encoding="utf-8") as f:
        leads = json.load(f)

    with users_json_path.open("r", encoding="utf-8") as f:
        users = json.load(f)

    # Filter out system users
    users = [u for u in users if u["email"] not in ["Administrator", "Guest"]]

    number_of_leads = min(len(leads), number_of_leads) if number_of_leads > 0 else len(leads)
    leads = fake.random_elements(elements=leads, length=number_of_leads, unique=True)

    semaphore = asyncio.Semaphore(32)
    tasks = []
    stats = {"tokens": 0}

    async def process_lead_content(lead):
        async with semaphore:
            lead_owner = next((u for u in users if u["email"] == lead["lead_owner"]), None)
            if not lead_owner:
                # If no specific lead owner found, use the first available user
                lead_owner = users[0] if users else {"email": "admin@example.com", "first_name": "Admin", "last_name": "User"}

            our_email = lead_owner["email"]
            their_email = lead["email"]
            our_full_name = f"{lead_owner['first_name']} {lead_owner['last_name']}"
            their_full_name = f"{lead['first_name']} {lead['last_name']}"
            number_of_emails = fake.random_int(emails_per_lead[0], emails_per_lead[1])
            number_of_notes = fake.random_int(notes_per_lead[0], notes_per_lead[1])
            number_of_tasks = fake.random_int(tasks_per_lead[0], tasks_per_lead[1])
            number_of_comments = fake.random_int(comments_per_lead[0], comments_per_lead[1])

            # Safely get mobile_no with fallback to empty string
            mobile_no = lead.get("mobile_no", "")

            logger.info(f"Generating content for lead {lead['email']} with {our_full_name} and {their_full_name}")
            email_conversation = await openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an assistant that generates realistic emails in a CRM system. 
                                    Generate professional, human-like emails for leads in the {settings.DATA_THEME_SUBJECT} industry.
                                    Each email should be unique and reflect authentic business interactions.""",
                    },
                    {
                        "role": "user",
                        "content": f"""Create a realistic CRM data including:
                                    1. Conversation consisting of {number_of_emails} emails between our employee {our_full_name} and the lead {their_full_name}.
                                    2. {number_of_notes} notes from employee {our_full_name} to our team, to note down key details about the lead and suitable actions to take.
                                    3. {number_of_tasks} tasks that our team including employee {our_full_name} needs to do to capture this lead.
                                    4. {number_of_comments} comments from the team about this lead or deal.
                                    The lead is in the {lead["industry"]} industry named {lead["organization"]}.
                                    The email should include:
                                    1. A brief, descriptive title
                                    2. Detailed content that sounds naturally written by a business professional
                                    3. Do not use Markdown formatting, use HTML for formatting

                                    Make it specific, with natural business language, varying tone, and authentic details.
                                    Avoid generic content and ensure it reads like something a real person would write in a CRM.

                                    Some additional information that can be helpful:
                                    - Today is {datetime.now().strftime("%Y-%m-%d")}
                                    - Lead phone number is {mobile_no}
                                    - Lead email is {their_email}
                                    - Lead's job title is {lead.get("job_title", "")}
                                    - Our company name is {settings.COMPANY_NAME}
                                    - Their company name is {lead["organization"]}
                                    """,
                    },
                ],
                response_format=LeadContent,
            )
            emails = email_conversation.choices[0].message.parsed.emails
            notes = email_conversation.choices[0].message.parsed.notes
            tasks = email_conversation.choices[0].message.parsed.tasks
            comments = email_conversation.choices[0].message.parsed.comments
            tokens = email_conversation.usage.total_tokens
            stats["tokens"] += tokens

            return {
                "lead": lead,
                "lead_owner": lead_owner,
                "our_email": our_email,
                "their_email": their_email,
                "our_full_name": our_full_name,
                "their_full_name": their_full_name,
                "emails": [
                    {
                        "subject": email.subject,
                        "body": email.body,
                        "sent_or_received": email.sent_or_received,
                    }
                    for email in emails
                ],
                "notes": [{"title": note.title, "content": note.content} for note in notes],
                "tasks": [{"title": task.title, "description": task.description} for task in tasks],
                "comments": [{"content": comment.content} for comment in comments],
                "users": users,  # Include users for comment assignment
            }

    for lead in leads:
        tasks.append(process_lead_content(lead))

    # Run all content generations concurrently but limited by the semaphore
    lead_content_data = await asyncio.gather(*tasks)
    logger.info(f"Total tokens used in generation: {stats['tokens']}")
    return lead_content_data


async def insert_lead_content_from_data(lead_content_data):
    """Insert lead content from cached data into the CRM system"""

    client = frappe_client.create_client()

    # Get current leads and create mapping by email+organization
    current_leads = client.get_list("CRM Lead", fields=["name", "email", "organization", "lead_owner"], limit_page_length=settings.LIST_LIMIT)
    # Map by email+organization to find actual database lead names and owners
    lead_mapping = {f"{lead['email']}-{lead['organization']}": {"name": lead["name"], "lead_owner": lead["lead_owner"]} for lead in current_leads}

    # Process in smaller batches to reduce server load
    BATCH_SIZE = 5  # Process 5 leads at a time
    total_batches = (len(lead_content_data) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(lead_content_data), BATCH_SIZE):
        batch = lead_content_data[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        logger.info(f"Processing batch {batch_num}/{total_batches}")

        # Process each item in the batch sequentially to avoid overload
        for content_item in batch:
            await process_single_lead_content(content_item, lead_mapping, client)

        # Add delay between batches
        if i + BATCH_SIZE < len(lead_content_data):
            await asyncio.sleep(2)  # 2 seconds between batches


async def process_single_lead_content(content_item, lead_mapping, client):
    """Process content for a single lead"""
    lead = content_item["lead"]

    # Map cached lead to actual database lead using email+organization
    lead_key = f"{lead['email']}-{lead['organization']}"
    if lead_key not in lead_mapping:
        logger.warning(f"Skipping content for non-existent lead: {lead['email']}")
        return

    # Use the actual database lead name and owner
    actual_lead_data = lead_mapping[lead_key]
    actual_lead_name = actual_lead_data["name"]
    actual_lead_owner = actual_lead_data["lead_owner"]

    our_email = content_item["our_email"]
    their_email = content_item["their_email"]
    our_full_name = content_item["our_full_name"]
    their_full_name = content_item["their_full_name"]

    # Insert emails with delays
    for email_data in content_item["emails"]:
        sent_or_received = email_data["sent_or_received"]
        email_doc = {
            "doctype": "Communication",
            "docstatus": 0,
            "idx": 0,
            "subject": email_data["subject"],
            "communication_medium": "Email",
            "recipients": their_email if sent_or_received == "Sent" else our_email,
            "sender": our_email if sent_or_received == "Sent" else their_email,
            "cc": None,
            "bcc": None,
            "phone_no": None,
            "delivery_status": "",
            "content": email_data["body"],
            "text_content": None,
            "communication_type": "Communication",
            "status": "Linked",
            "sent_or_received": sent_or_received,
            "communication_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "read_receipt": 0,
            "send_after": None,
            "sender_full_name": our_full_name if sent_or_received == "Sent" else their_full_name,
            "read_by_recipient": 0,
            "read_by_recipient_on": None,
            "reference_doctype": "CRM Lead",
            "reference_name": actual_lead_name,
            "reference_owner": actual_lead_owner,
            "email_account": "Replies",
            "in_reply_to": None,
            "user": actual_lead_owner,
            "email_template": None,
            "unread_notification_sent": 0,
            "seen": 1,
            "email_status": "Open",
            "has_attachment": 0,
        }

        try:
            client.insert(email_doc)
            await asyncio.sleep(0.1)  # Small delay between emails
        except Exception as e:
            logger.error(e)

    # Insert notes with delays
    for note_data in content_item["notes"]:
        note_doc = {
            "doctype": "FCRM Note",
            "title": note_data["title"],
            "content": note_data["content"],
            "reference_doctype": "CRM Lead",
            "reference_docname": actual_lead_name,
        }
        try:
            client.insert(note_doc)
            await asyncio.sleep(0.1)  # Small delay between notes
        except Exception as e:
            logger.error(e)

    # Insert tasks with delays
    for task_data in content_item["tasks"]:
        task_doc = {
            "doctype": "CRM Task",
            "reference_doctype": "CRM Lead",
            "reference_docname": actual_lead_name,
            "title": task_data["title"],
            "description": task_data["description"],
            "assigned_to": our_email,
            "due_date": fake.date_time_between(start_date="-28d", end_date="now").strftime("%Y-%m-%d %H:%M:%S"),
            "priority": fake.random_element(["High", "Medium", "Low"]),
            "status": fake.random_element(
                OrderedDict(
                    [
                        ("Backlog", 0.1),
                        ("Todo", 0.2),
                        ("In Progress", 0.2),
                        ("Done", 0.4),
                        ("Canceled", 0.1),
                    ]
                )
            ),
        }
        try:
            client.insert(task_doc)
            await asyncio.sleep(0.1)  # Small delay between tasks
        except Exception as e:
            logger.error(e)

    # Insert comments with delays - use synchronous calls
    for comment_data in content_item["comments"]:
        comment_doc = {
            "owner": "Administrator",  # Use admin instead of random users
            "docstatus": 0,
            "doctype": "Comment",
            "comment_type": "Comment",
            "content": comment_data["content"],
            "reference_doctype": "CRM Lead",
            "reference_name": actual_lead_name,
        }
        try:
            client.insert(comment_doc)  # Use synchronous call instead of async
            await asyncio.sleep(0.1)  # Small delay between comments
        except Exception as e:
            logger.error(f"Error adding comment {comment_data['content'][:50]}... to lead {actual_lead_name}: {e}")


async def delete_leads():
    client = frappe_client.create_client()

    leads = client.get_list(
        "CRM Lead",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for lead in leads:
        try:
            client.delete("CRM Lead", lead["name"])
            logger.info(f"Deleted lead {lead['name']}")
        except Exception as e:
            logger.error(e)


async def delete_calls():
    client = frappe_client.create_client()

    calls = client.get_list(
        "CRM Call Log",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for call in calls:
        try:
            client.delete("CRM Call Log", call["name"])
            logger.info(f"Deleted call {call['name']}")
        except Exception as e:
            logger.error(e)


async def delete_emails():
    client = frappe_client.create_client()
    emails = client.get_list(
        "Communication",
        fields=["name"],
        filters=[["communication_medium", "=", "Email"]],
        limit_page_length=settings.LIST_LIMIT,
    )
    for email in emails:
        try:
            client.delete("Communication", email["name"])
            logger.info(f"Deleted email {email['name']}")
        except Exception as e:
            logger.error(e)


async def delete_tasks():
    client = frappe_client.create_client()
    tasks = client.get_list(
        "CRM Task",
        fields=["name"],
        limit_page_length=settings.LIST_LIMIT,
    )
    for task in tasks:
        try:
            client.delete("CRM Task", task["name"])
            logger.info(f"Deleted task {task['name']}")
        except Exception as e:
            logger.error(f"Error deleting task {task['name']}: {e}")
