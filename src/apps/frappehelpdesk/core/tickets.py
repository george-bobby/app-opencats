import asyncio
import json
import random
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.core.customers import (
    CUSTOMER_USERS_CACHE_FILE,
    CUSTOMERS_CACHE_FILE,
)
from apps.frappehelpdesk.core.teams import TEAM_ASSIGNMENTS_CACHE_FILE, TEAMS_CACHE_FILE
from apps.frappehelpdesk.utils.constants import HD_TICKET_TYPES
from apps.frappehelpdesk.utils.database import create_mariadb_client
from apps.frappehelpdesk.utils.frappe_client import AuthError, FrappeClient
from common.logger import logger


fake = Faker()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
# Cache file path for tickets
TICKETS_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "tickets.json")
BATCH_SIZE = 100


class Ticket(BaseModel):
    subject: str = Field(description="The subject of this ticket. Make sure this is unique")
    description: str = Field(description="The description of the ticket, use plain text format, use HTML for formatting.")
    agent_group: str = Field(description="The agent group that should handle this ticket, should be one of the existing agent groups.")
    ticket_type: str = Field(description="The type of the ticket, should be one of the existing ticket types.")
    timestamp: float = Field(description="The timestamp of the ticket, in seconds since epoch.")
    conversation_date: str = Field(
        default="",
        description="The date when this conversation took place, in YYYY-MM-DD format.",
    )
    rating: int = Field(
        description="The rating of the ticket, should be a number from 1 to 5.",
        ge=1,
        le=5,
    )


class Comment(BaseModel):
    content: str = Field(description="The comment to be added to the ticket,  use HTML for formatting.")
    commented_by: str = Field(description="The commenter of the ticket, should be one of the existing agents.")


class Reply(BaseModel):
    content: str = Field(description="The reply to the ticket of the original creator, use HTML for formatting.")
    replied_by: str = Field(description="The replier of the ticket, should be one of the existing agents, but make it make sense in the context of the ticket.")


class ConversationItem(BaseModel):
    type: Literal["comment", "reply", "customer_response", "status_change"] = Field(  # noqa: A003, RUF100
        description="Whether this is an internal comment, an agent reply to customer, a customer response back to agents, or a status change"
    )
    content: str = Field(description="The content of the comment or reply, use HTML for formatting.")
    author: str = Field(description="The agent who created this comment/reply, or the customer email for customer responses")
    sequence: int = Field(description="The order in the conversation (1, 2, 3, etc.)")
    status: str = Field(
        default="",
        description="For status_change type: the new status to set (Open, Closed, Replied, Resolved)",
    )
    priority: str = Field(
        default="",
        description="For status_change type: the new priority to set. MUST be exactly one of: Low, Medium, High, Urgent",
    )
    reason: str = Field(
        default="",
        description="For status_change type: the reason for the status/priority change",
    )
    timestamp: float = Field(
        default=0.0,
        description="The timestamp when this conversation item was created, in seconds since epoch",
    )


class TicketData(BaseModel):
    ticket: Ticket
    conversation: list[ConversationItem] = Field(
        description="""Generate 5-8 conversation items in chronological order.
        Mix internal comments, agent replies, customer responses, and status changes realistically:
        - Start with internal triage/assessment comments (type: "comment")
        - Follow with agent replies to customer (type: "reply")
        - Include customer responses back to agents (type: "customer_response")
        - Include internal progress updates (type: "comment")
        - Add realistic status changes (type: "status_change") when appropriate
        - End with resolution or status updates
        Each item should have a sequence number (1, 2, 3, etc.) indicating chronological order.
        
        For status_change items:
        - Set the status field to the new status (Open, Closed, Replied, Resolved)
        - Set the priority field to the new priority ONLY using these exact values: Low, Medium, High, Urgent
        - Include a reason field explaining why the change was made
        - Use content field for any additional notes about the change
        
        CRITICAL PRIORITY RULE: Priority field must be exactly one of these four values:
        "Low", "Medium", "High", "Urgent" - no other values are allowed!"""
    )


def generate_realistic_timestamps(conversation_items, ticket_creation_datetime):
    """
    Generate realistic timestamps for conversation items based on business hours.
    All timestamps will be after the ticket creation time and before today.

    Args:
        conversation_items: List of ConversationItem objects sorted by sequence
        ticket_creation_datetime: The datetime when the ticket was created

    Returns:
        None (modifies conversation_items in place)
    """
    # Start from the ticket creation time
    current_time = ticket_creation_datetime

    # Add a small delay (2-10 minutes) after ticket creation for the first conversation item
    initial_delay_minutes = fake.random_int(min=2, max=10)
    current_time += timedelta(minutes=initial_delay_minutes)

    # Ensure the first item starts within business hours
    current_time = adjust_to_business_hours(current_time)

    for i, item in enumerate(conversation_items):
        if i == 0:
            # First item starts after ticket creation with the initial delay applied
            pass  # current_time is already set above
        else:
            # Subsequent items have faster, more realistic delays for quicker resolution
            if item.type == "comment":
                # Internal comments: 2-10 minutes after previous item
                delay_minutes = fake.random_int(min=2, max=10)
            elif item.type == "reply":
                # Agent replies: 5-20 minutes after previous item (faster response times)
                delay_minutes = fake.random_int(min=5, max=20)
            elif item.type == "customer_response":
                # Customer responses: 10-60 minutes after agent reply (faster customer responses)
                delay_minutes = fake.random_int(min=10, max=60)
            elif item.type == "status_change":
                # Status changes: 1-5 minutes after related action
                delay_minutes = fake.random_int(min=1, max=5)
            else:
                delay_minutes = fake.random_int(min=5, max=15)

            current_time += timedelta(minutes=delay_minutes)

            # Ensure we stay within business hours (9 AM - 6 PM, weekdays only)
            current_time = adjust_to_business_hours(current_time)

        # Ensure timestamp is not in the future (before today)
        now = datetime.now()
        if current_time > now:
            current_time = now - timedelta(minutes=fake.random_int(min=5, max=60))
            current_time = adjust_to_business_hours(current_time)

        item.timestamp = current_time.timestamp()


def adjust_to_business_hours(dt):
    """
    Adjust datetime to fall within business hours (9 AM - 6 PM, Monday-Friday).
    If outside business hours, move to the next business hour.
    """
    # If it's weekend, move to Monday
    while dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
        dt = dt + timedelta(days=1)
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)

    # If before 9 AM, set to 9 AM
    if dt.hour < 9:
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    # If after 6 PM, move to next day 9 AM
    elif dt.hour >= 18:
        dt = dt + timedelta(days=1)
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        # Check if the next day is weekend
        dt = adjust_to_business_hours(dt)

    return dt


async def insert_single_ticket(ticket_data, contact, customer_name):
    logger.info(f"Inserting ticket: {ticket_data.ticket.subject} for {customer_name} by {contact['name']}.")
    op_email = contact["email_id"]
    db_client = await create_mariadb_client()

    try:
        async with FrappeClient(username=op_email, password=settings.USER_PASSWORD) as client:
            inserted_ticket = await client.insert(
                {
                    "doctype": "HD Ticket",
                    "subject": ticket_data.ticket.subject,
                    "description": ticket_data.ticket.description,
                    "agent_group": ticket_data.ticket.agent_group,
                    "ticket_type": ticket_data.ticket.ticket_type,
                    "customer": customer_name,
                }
            )
            inserted_ticket_id = int(inserted_ticket["name"])
            await db_client.execute(
                "UPDATE `tabHD Ticket` SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s) WHERE name = %s",
                (
                    ticket_data.ticket.timestamp,
                    ticket_data.ticket.timestamp,
                    inserted_ticket_id,
                ),
            )
            await db_client.execute(
                "UPDATE `tabCommunication` SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s), communication_date = FROM_UNIXTIME(%s) WHERE reference_name = %s",
                (
                    ticket_data.ticket.timestamp,
                    ticket_data.ticket.timestamp,
                    ticket_data.ticket.timestamp,
                    inserted_ticket_id,
                ),
            )

    except (AuthError, Exception) as e:
        logger.warning(f"Error creating ticket for {op_email}: {e}")
        return

    if not inserted_ticket:
        return

    # Sort conversation items by sequence to ensure chronological order
    sorted_conversation = sorted(ticket_data.conversation, key=lambda item: item.sequence)

    # Insert conversation items in chronological order and update status accordingly
    current_status = None  # Initial status
    current_priority = "Medium"
    main_handler = ""
    first_response_sent = False

    for item in sorted_conversation:
        try:
            if item.type == "comment":
                if not main_handler:
                    main_handler = item.author
                async with FrappeClient(username=item.author, password=settings.USER_PASSWORD) as client:
                    inserted_comment = await client.insert(
                        {
                            "doctype": "HD Ticket Comment",
                            "docstatus": 0,
                            "name": f"new-hd-ticket-comment-{fake.bothify('?????#####')}",
                            "owner": item.author,
                            "is_pinned": 0,
                            "reference_ticket": inserted_ticket_id,
                            "commented_by": item.author,
                            "content": item.content,
                        }
                    )
                    inserted_comment_id = inserted_comment["name"]
                    await db_client.execute(
                        "UPDATE `tabHD Ticket Comment` SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s) WHERE name = %s",
                        (
                            item.timestamp,
                            item.timestamp,
                            inserted_comment_id,
                        ),
                    )

            elif item.type == "reply":
                main_handler = item.author
                # Insert agent reply to customer
                async with FrappeClient() as client:
                    # Convert timestamp to UTC for communication_date without timezone suffix
                    communication_date = datetime.fromtimestamp(item.timestamp, tz=UTC).replace(tzinfo=None).isoformat()
                    inserted_reply = await client.insert(
                        {
                            "docstatus": 0,
                            "doctype": "Communication",
                            "name": f"new-communication-{fake.bothify('?????#####')}",
                            "owner": item.author,
                            "communication_medium": "Email",
                            "delivery_status": "",
                            "communication_type": "Communication",
                            "comment_type": "",
                            "status": "Linked",
                            "sent_or_received": "Sent",
                            "communication_date": communication_date,
                            "read_receipt": 0,
                            "read_by_recipient": 0,
                            "user": item.author,
                            "unread_notification_sent": 0,
                            "seen": 0,
                            "email_status": "Open",
                            "has_attachment": 0,
                            "subject": f"Re: {inserted_ticket['subject']}",
                            "sender": item.author,
                            "recipients": op_email,
                            "content": item.content,
                            "reference_doctype": "HD Ticket",
                            "reference_name": inserted_ticket_id,
                            "reference_owner": op_email,
                            "email_account": "Replies",
                            "rating": 0,
                        }
                    )
                    inserted_reply_id = inserted_reply["name"]
                    await db_client.execute(
                        "UPDATE `tabCommunication` SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s) WHERE name = %s",
                        (
                            item.timestamp,
                            item.timestamp,
                            inserted_reply_id,
                        ),
                    )
                if not first_response_sent:
                    first_response_sent = True
                    # Update ticket status to "Replied" after the first agent reply
                    await db_client.execute(
                        "UPDATE `tabHD Ticket` SET first_responded_on = FROM_UNIXTIME(%s) WHERE name = %s",
                        (item.timestamp, inserted_ticket_id),
                    )

            elif item.type == "customer_response":
                async with FrappeClient() as client:
                    # Convert timestamp to UTC for communication_date without timezone suffix
                    inserted_reply = await client.insert(
                        {
                            "docstatus": 0,
                            "doctype": "Communication",
                            "name": f"new-communication-{fake.bothify('?????#####')}",
                            "owner": item.author,
                            "communication_medium": "Email",
                            "delivery_status": "",
                            "communication_type": "Communication",
                            "comment_type": "",
                            "status": "Linked",
                            "sent_or_received": "Received",
                            # "communication_date": datetime.fromtimestamp(
                            #     item.timestamp
                            # ).isoformat(),
                            "read_receipt": 0,
                            "read_by_recipient": 0,
                            "user": item.author,
                            "unread_notification_sent": 0,
                            "seen": 0,
                            "email_status": "Open",
                            "has_attachment": 0,
                            "subject": f"Re: {inserted_ticket['subject']}",
                            "sender": item.author,
                            "content": item.content,
                            "reference_doctype": "HD Ticket",
                            "reference_name": inserted_ticket_id,
                            "reference_owner": item.author,
                            "rating": 0,
                        }
                    )

                    inserted_reply_id = inserted_reply["name"]
                    await db_client.execute(
                        """UPDATE `tabCommunication` 
                        SET creation = FROM_UNIXTIME(%s),
                            modified = FROM_UNIXTIME(%s),
                            communication_date = FROM_UNIXTIME(%s)
                        WHERE name = %s""",
                        (
                            item.timestamp,
                            item.timestamp,
                            item.timestamp,
                            inserted_reply_id,
                        ),
                    )
                    await db_client.execute(
                        """
                            UPDATE `tabHD Ticket Activity` 
                            SET creation = FROM_UNIXTIME(%s), 
                                modified = FROM_UNIXTIME(%s),
                                modified_by = %s,
                                owner = %s
                            WHERE ticket = %s
                            ORDER BY creation DESC
                            LIMIT 1
                        """,
                        (
                            item.timestamp,
                            item.timestamp,
                            item.author,
                            item.author,
                            inserted_ticket_id,
                        ),
                    )

            elif item.type == "status_change":
                # Handle GPT-generated status and priority changes
                async with FrappeClient(username=item.author, password=settings.USER_PASSWORD) as author_client:
                    if item.status and item.status != current_status:
                        await author_client.set_value(
                            "HD Ticket",
                            inserted_ticket_id,
                            "status",
                            item.status,
                        )
                        current_status = item.status
                        logger.info(f"Updated ticket status to: {item.status} - {item.reason}")
                        # Update timestamp for latest activity record
                        await db_client.execute(
                            """
                            UPDATE `tabHD Ticket Activity` 
                            SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s)
                            WHERE ticket = %s
                            ORDER BY creation DESC
                            LIMIT 1
                            """,
                            (
                                item.timestamp,
                                item.timestamp,
                                inserted_ticket_id,
                            ),
                        )
                        if current_status == "Resolved":
                            # Set resolution date when ticket is resolved
                            await db_client.execute(
                                "UPDATE `tabHD Ticket` SET resolution_time = %s WHERE name = %s",
                                (
                                    int(item.timestamp - ticket_data.ticket.timestamp),
                                    inserted_ticket_id,
                                ),
                            )

                    if item.priority and item.priority != current_priority:
                        # Validate priority value - only allow valid Frappe helpdesk priorities
                        valid_priorities = ["Low", "Medium", "High", "Urgent"]
                        if item.priority in valid_priorities:
                            await author_client.set_value(
                                "HD Ticket",
                                inserted_ticket["name"],
                                "priority",
                                item.priority,
                            )
                            current_priority = item.priority
                            await db_client.execute(
                                """
                                UPDATE `tabHD Ticket Activity` 
                                SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s)
                                WHERE ticket = %s
                                ORDER BY creation DESC
                                LIMIT 1
                                """,
                                (
                                    item.timestamp,
                                    item.timestamp,
                                    inserted_ticket_id,
                                ),
                            )
                        else:
                            logger.warning(f"Invalid priority '{item.priority}' ignored. Valid values: {valid_priorities}")

                    if item.content:
                        inserted_comment = await author_client.insert(
                            {
                                "doctype": "HD Ticket Comment",
                                "docstatus": 0,
                                "name": f"new-hd-ticket-comment-{fake.bothify('?????#####')}",
                                "owner": item.author,
                                "is_pinned": 0,
                                "reference_ticket": inserted_ticket_id,
                                "commented_by": item.author,
                                "content": item.content,
                            }
                        )
                        inserted_comment_id = inserted_comment["name"]
                        await db_client.execute(
                            "UPDATE `tabHD Ticket Comment` SET creation = FROM_UNIXTIME(%s), modified = FROM_UNIXTIME(%s) WHERE name = %s",
                            (
                                item.timestamp,
                                item.timestamp,
                                inserted_comment_id,
                            ),
                        )

        except (AuthError, Exception) as e:
            logger.warning(f"Error inserting {item.type} by {item.author}: {e}")
            continue  # Continue with next item even if one fails

    if current_status != "Open":
        # Convert 1-5 rating to 0.2-1.0 scale for feedback_rating
        normalized_rating = round(ticket_data.ticket.rating / 5, 2)
        await db_client.execute(
            "UPDATE `tabHD Ticket` SET feedback_rating = %s WHERE name = %s",
            (normalized_rating, inserted_ticket_id),
        )

    # Final status is now handled by GPT-generated status_change items in the conversation
    # No need for automatic final status setting
    logger.info(f"Ticket processing completed. Final status: {current_status}")


async def generate_tickets(number_of_tickets: int, tickets_per_batch: int = BATCH_SIZE):
    """
    Generate tickets using OpenAI and save to JSON cache file.
    Always generates fresh data and overwrites existing cache.
    Uses data from JSON files instead of Frappe client.
    """
    logger.start(f"Generating {number_of_tickets} tickets...")

    # Load data from JSON files
    try:
        # Load contacts
        if not CUSTOMER_USERS_CACHE_FILE.exists():
            logger.fail("Contacts cache file not found. Please generate customer users first.")
            return
        with CUSTOMER_USERS_CACHE_FILE.open() as f:
            contacts_data = json.load(f)
            # Extract contact information from the nested structure
            contacts = []
            for contact_doc in contacts_data.get("contact_docs", []):
                if contact_doc.get("email_ids"):
                    email_id = contact_doc["email_ids"][0]["email_id"]
                    # Skip company domain emails
                    if not email_id.endswith(f"@{settings.COMPANY_DOMAIN}") and not email_id.endswith("@example.com"):
                        contacts.append(
                            {
                                "name": contact_doc.get("full_name", ""),
                                "email_id": email_id,
                                "full_name": contact_doc.get("full_name", ""),
                            }
                        )

        # Load teams
        if not TEAMS_CACHE_FILE.exists():
            logger.fail("Teams cache file not found. Please generate teams first.")
            return
        with TEAMS_CACHE_FILE.open() as f:
            teams_data = json.load(f)
            teams = [{"name": team["team_name"]} for team in teams_data]

        # Load team assignments to get team members
        if not TEAM_ASSIGNMENTS_CACHE_FILE.exists():
            logger.fail("Team assignments cache file not found. Please generate team assignments first.")
            return
        with TEAM_ASSIGNMENTS_CACHE_FILE.open() as f:
            team_assignments_data = json.load(f)

        # Load customers
        if not CUSTOMERS_CACHE_FILE.exists():
            logger.fail("Customers cache file not found. Please generate customers first.")
            return
        with CUSTOMERS_CACHE_FILE.open() as f:
            customers_data = json.load(f)

        # Use ticket types from constants
        ticket_types = [{"name": ticket_type["name"]} for ticket_type in HD_TICKET_TYPES]

    except (json.JSONDecodeError, Exception) as e:
        logger.fail(f"Error loading data from JSON files: {e}")
        return

    if not contacts:
        logger.fail("No valid contacts found in cache file")
        return

    if not teams:
        logger.fail("No teams found in cache file")
        return

    logger.info(f"Generating exactly {number_of_tickets} tickets using cached data")
    generated_tickets = []
    max_attempts = number_of_tickets * 2  # Allow up to 2x attempts to handle failures
    attempts = 0

    # Keep generating until we have enough tickets or reach max attempts
    while len(generated_tickets) < number_of_tickets and attempts < max_attempts:
        # Calculate how many more tickets we need
        tickets_needed = number_of_tickets - len(generated_tickets)
        # Generate exactly what we need, up to a reasonable batch size
        batch_size = min(tickets_needed, tickets_per_batch)

        logger.info(f"Generating batch of {batch_size} tickets (have {len(generated_tickets)}, need {number_of_tickets})")

        # Create a function that generates a single ticket
        async def create_single_ticket():
            max_retries = 3
            for retry in range(max_retries):
                try:
                    contact = fake.random_element(contacts)

                    if not contact:
                        continue

                    contact_domain = contact["email_id"].split("@")[1]

                    # Find customer by domain
                    customer_list = [c for c in customers_data if c.get("domain") == contact_domain]
                    if not customer_list:
                        continue
                    customer_name = customer_list[0]["customer_name"]

                    ticket_type = fake.random_element(ticket_types)
                    team = fake.random_element(teams)

                    # Get team members from team assignments
                    team_assignment = next(
                        (ta for ta in team_assignments_data if ta["team_name"] == team["name"]),
                        None,
                    )
                    if not team_assignment or not team_assignment.get("members"):
                        continue
                    all_team_users = [member["user"] for member in team_assignment["members"]]

                    # Ensure we have enough team members for comments and replies
                    if len(all_team_users) < 2:
                        continue

                    # Randomly select maximum 3 team members for this ticket
                    max_agents = min(3, len(all_team_users))
                    team_users = fake.random_elements(elements=all_team_users, length=max_agents, unique=True)

                    # Generate end status with specified distribution
                    end_status = random.choices(
                        population=["Open", "Replied", "Closed", "Resolved"],
                        weights=[15, 15, 20, 50],  # Open: 15%, Replied: 15%, Closed: 20%, Resolved: 50%
                        k=1,
                    )[0]

                    # Generate conversation datetime based on end status
                    # Open and Replied tickets: recent conversations (last 2 weeks)
                    # Closed/Resolved tickets: can be older (last 12 months, but not too recent)
                    if end_status in ["Open", "Replied"]:
                        conversation_datetime = fake.date_time_between(start_date="-14d", end_date="-1d")
                    else:
                        conversation_datetime = fake.date_time_between(start_date="-12M", end_date="-3d")
                    conversation_date_str = conversation_datetime.strftime("%Y-%m-%d")

                    # Return ticket generation parameters instead of generating immediately
                    return {
                        "contact": contact,
                        "customer_name": customer_name,
                        "ticket_type": ticket_type,
                        "team": team,
                        "team_users": team_users,
                        "end_status": end_status,
                        "conversation_datetime": conversation_datetime,
                        "conversation_date_str": conversation_date_str,
                    }

                except Exception as e:
                    logger.warning(f"Error preparing ticket data (attempt {retry + 1}/{max_retries}): {e}")
                    if retry == max_retries - 1:
                        return None
                    await asyncio.sleep(0.1)  # Brief delay before retry

            return None

        # Generate ticket parameters for the entire batch
        logger.info(f"Preparing {batch_size} ticket parameters...")
        ticket_params_tasks = [create_single_ticket() for _ in range(batch_size)]
        ticket_params_results = await asyncio.gather(*ticket_params_tasks)
        valid_ticket_params = [params for params in ticket_params_results if params is not None]

        if not valid_ticket_params:
            logger.warning("No valid ticket parameters generated in this batch")
            attempts += batch_size
            continue

        logger.info(f"Generated {len(valid_ticket_params)} valid ticket parameters, now generating tickets with OpenAI...")

        # Generate all tickets simultaneously with OpenAI
        async def generate_single_ticket_with_ai(params):
            try:
                ticket = await openai_client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are a helpful assistant that creates realistic helpdesk tickets with detailed conversation threads. 
                            Create tickets that have substantial back-and-forth communication with multiple comments and replies that tell a complete story of issue resolution.
                            Focus on generating realistic, coherent conversations that demonstrate proper customer support workflows.
                            
                            CRITICAL REQUIREMENT: This ticket MUST end with the status: {params["end_status"]}

                            TICKET CREATION REQUIREMENTS:
                            Create a realistic helpdesk ticket with:
                            1. A brief, descriptive title
                            2. Detailed content that sounds naturally written by a customer
                            3. HTML formatting (not Markdown)
                            4. Content authentic to the conversation date: {params["conversation_date_str"]}
                            5. A rating from 1-5 (never 0) based on final status and resolution quality
                            6. Ticket type: {params["ticket_type"]["name"]}
                            
                            Consider seasonal context, business cycles, or time-relevant issues for authenticity.
                            Avoid generic content and ensure it reads like something a real customer would write.
                            Information should be specific to the customer and their company context.

                            CONVERSATION THREAD REQUIREMENTS:
                            Create a chronological conversation thread with 5-8 items mixing these types:
                            - type: "comment" for internal agent notes and thoughts
                            - type: "reply" for agent responses to the customer
                            - type: "customer_response" for customer responses back to the agent
                            - type: "status_change" for explicit status or priority changes with reasons

                            Each conversation item must include:
                            - content: The actual message content using HTML formatting
                            - author: Agent email for comments/replies, customer email for customer_response items
                            - sequence: Chronological order number (1, 2, 3, etc.)
                            - status: (status_change only) the new status to set
                            - priority: (status_change only) MUST be exactly one of: "Low", "Medium", "High", "Urgent"
                            - reason: (status_change only) explanation for the change

                            STATUS-SPECIFIC CONVERSATION FLOWS:

                            For "Open" status (ongoing conversation - 15%):
                            The conversation MUST be recent and ongoing. Create a scenario where the customer is still waiting for an agent reply, 
                            or the agent is waiting for more information from the customer. The conversation should NOT be finished - it should 
                            feel like it's still in progress with pending actions.
                            1. Start with internal agent comment about the ticket (type: "comment") 
                            2. Agent sends initial response to customer (type: "reply")
                            3. Add status change to "Replied" (type: "status_change") with reason
                            4. Customer responds back (type: "customer_response")
                            5. Add status change back to "Open" (type: "status_change") 
                            6. Include internal agent progress notes or escalation (type: "comment")
                            7. End with the conversation still in progress - either waiting for customer information or agent working on solution (no final resolution)
                            
                            For "Replied" status (waiting for customer response - 15%):
                            The conversation should show that the agent has responded to the customer and is now waiting for the customer to reply back. 
                            The last interaction should be an agent reply to customer, with no further customer response yet. 
                            This represents tickets where agents have provided solutions or asked for more information and are waiting for customer feedback.
                            1. Start with internal agent comment about the ticket (type: "comment")
                            2. Agent sends initial response to customer (type: "reply")
                            3. Add status change to "Replied" (type: "status_change") with reason
                            4. Optionally include customer response and additional agent reply
                            5. End with final agent reply to customer (type: "reply")
                            6. Add final status change to "Replied" confirming agent is waiting for customer
                            7. Do NOT include final customer response - ticket should end waiting for customer
                            
                            For "Closed" status (no resolution possible - 20%):
                            The conversation should show that no resolution could be reached, or agents determined they cannot help further. 
                            This could be due to: customer not responding after multiple attempts, issue being outside scope of support, 
                            customer canceling request, or technical limitations preventing resolution.
                            1. Start with internal agent comment about the ticket (type: "comment")
                            2. Agent sends initial response to customer (type: "reply")
                            3. Add status change to "Replied" (type: "status_change") with reason
                            4. Customer responds back (type: "customer_response") 
                            5. Include multiple attempts to help (more replies and responses)
                            6. Add internal comments showing challenges or limitations
                            7. End with status change to "Closed" explaining why no resolution was possible
                            
                            For "Resolved" status (successful resolution - 50%):
                            The conversation should show a complete resolution where the customer's issue was successfully solved. 
                            Include confirmation from the customer that the solution worked, or clear documentation that the issue has been fixed.
                            1. Start with internal agent comment about the ticket (type: "comment")
                            2. Agent sends initial response to customer (type: "reply")
                            3. Add status change to "Replied" (type: "status_change") with reason
                            4. Customer responds back (type: "customer_response")
                            5. Include working solution attempts and progress updates
                            6. Agent provides successful solution (type: "reply")
                            7. Customer confirms solution worked (type: "customer_response")
                            8. End with status change to "Resolved" (type: "status_change")

                            STATUS CHANGE GUIDELINES:
                            - Use status_change items to explicitly update ticket status during conversation
                            - Common status transitions: Open → Replied → Open → Resolved/Closed
                            - Include priority changes when circumstances change (escalations, urgency, etc.)
                            - Always provide a clear reason for status/priority changes
                            - Status changes should feel natural and follow logical workflow
                            - Ticket starts as "Open", first agent reply changes to "Replied", customer responses typically change back to "Open"
                            - Priority can be adjusted based on conversation content and escalations

                            VALID PRIORITY VALUES (use EXACTLY these values):
                            - "Low" (40%): Routine issues, minor bugs, documentation requests
                            - "Medium" (35%): Standard technical issues, non-critical bugs
                            - "High" (20%): Service disruptions, major features unavailable
                            - "Urgent" (5%): System down, data loss, security issues
                            MANDATORY: Priority must be exactly one of these four strings: "Low", "Medium", "High", "Urgent"

                            RATING REQUIREMENTS (1-5 scale, never 0):
                            - For "Open" tickets: Lower ratings (1-3) as customer may be frustrated with ongoing issues
                            - For "Replied" tickets: Moderate ratings (2-4) as agent has responded but issue not yet resolved
                            - For "Closed" tickets: Lower ratings (1-3) reflecting customer dissatisfaction with unresolved issues  
                            - For "Resolved" tickets: Higher ratings (3-5) reflecting successful resolution
                            Rating scale meaning:
                            - 1-2: Dissatisfied with service or outcome
                            - 3: Neutral or somewhat satisfied
                            - 4: Satisfied with service and resolution
                            - 5: Extremely satisfied, excellent service

                            AUTHOR ASSIGNMENT RULES:
                            - For type "comment" and "reply": Only use agent emails from: {", ".join(params["team_users"])}
                            - For type "customer_response": Always use customer email: {params["contact"]["email_id"]}
                            - While up to THREE agents can be involved, all replies and status changes should come from the same agent for consistency
                            - Do not use any other email addresses not mentioned above

                            CONVERSATION QUALITY REQUIREMENTS:
                            - Tell a complete story from initial triage to final status
                            - Internal comments should be concise and informal
                            - Agent replies should be professional and customer-focused
                            - Customer responses should sound natural and authentic
                            - Each conversation item should build upon the previous context
                            - Use HTML formatting and make content professional but conversational
                            - Ensure the entire thread tells a coherent story that naturally leads to the final status
                            - The conversation flow should feel authentic and justify why the ticket ends in the specified state

                            CONTEXT INFORMATION:
                            - Conversation date: {params["conversation_date_str"]}
                            - Today's date: {datetime.now().strftime("%Y-%m-%d")} (for reference)
                            - Helpdesk system for: {settings.DATA_THEME_SUBJECT}
                            - Ticket creator: {params["contact"]["full_name"]} ({params["contact"]["email_id"]}) from {params["customer_name"]}
                            - Assigned team: {params["team"]["name"]}
                            - Available agents: {", ".join(params["team_users"])}
                            """,
                        },
                    ],
                    response_format=TicketData,
                )

                ticket_data = ticket.choices[0].message.parsed
                ticket_data.ticket.ticket_type = params["ticket_type"]["name"]
                ticket_data.ticket.agent_group = params["team"]["name"]
                ticket_data.ticket.conversation_date = params["conversation_date_str"]
                # Set timestamp to match the conversation date
                ticket_data.ticket.timestamp = params["conversation_datetime"].timestamp()

                # Generate realistic timestamps for conversation items starting after ticket creation
                ticket_creation_datetime = datetime.fromtimestamp(ticket_data.ticket.timestamp)
                generate_realistic_timestamps(ticket_data.conversation, ticket_creation_datetime)

                # Validate and fix author assignments for conversation items
                for item in ticket_data.conversation:
                    if item.type == "customer_response":
                        # Customer responses should be authored by the customer
                        item.author = params["contact"]["email_id"]
                    else:
                        # Comments and replies should be authored by team members
                        # If AI used an invalid email, assign to a random team member
                        if item.author not in params["team_users"]:
                            item.author = fake.random_element(params["team_users"])

                # Store complete ticket data for caching
                cached_ticket = {
                    "ticket_data": {
                        "ticket": {
                            "subject": ticket_data.ticket.subject,
                            "description": ticket_data.ticket.description,
                            "agent_group": ticket_data.ticket.agent_group,
                            "ticket_type": ticket_data.ticket.ticket_type,
                            "timestamp": ticket_data.ticket.timestamp,
                            "conversation_date": ticket_data.ticket.conversation_date,
                            "rating": ticket_data.ticket.rating,
                        },
                        "conversation": [
                            {
                                "type": item.type,
                                "content": item.content,
                                "author": item.author,
                                "sequence": item.sequence,
                                "status": getattr(item, "status", ""),
                                "priority": getattr(item, "priority", ""),
                                "reason": getattr(item, "reason", ""),
                                "timestamp": getattr(item, "timestamp", 0.0),
                            }
                            for item in ticket_data.conversation
                        ],
                    },
                    "contact": {
                        "name": params["contact"]["name"],
                        "email_id": params["contact"]["email_id"],
                        "full_name": params["contact"]["full_name"],
                    },
                    "customer_name": params["customer_name"],
                    "team_name": params["team"]["name"],
                    "ticket_type_name": params["ticket_type"]["name"],
                }

                return cached_ticket

            except Exception as e:
                logger.warning(f"Error generating ticket with AI: {e}")
                return None

        # Create semaphore to limit concurrent OpenAI requests
        semaphore = asyncio.Semaphore(20)  # Increased from 16 for better throughput

        async def generate_with_semaphore(params, sem=semaphore):
            async with sem:
                return await generate_single_ticket_with_ai(params)

        # Generate all tickets simultaneously
        ai_tasks = [generate_with_semaphore(params) for params in valid_ticket_params]
        results = await asyncio.gather(*ai_tasks, return_exceptions=True)
        batch_tickets = [result for result in results if result is not None and not isinstance(result, Exception)]
        generated_tickets.extend(batch_tickets)

        attempts += len(valid_ticket_params)
        logger.info(f"Generated {len(batch_tickets)} tickets in this batch, total: {len(generated_tickets)}")

    # Check if we generated fewer tickets than requested
    if len(generated_tickets) < number_of_tickets:
        logger.warning(f"Only generated {len(generated_tickets)} tickets out of {number_of_tickets} requested after {attempts} attempts")

    # Save to cache
    try:
        # Ensure the data directory exists
        TICKETS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {"tickets": generated_tickets}

        with TICKETS_CACHE_FILE.open("w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Cached {len(generated_tickets)} tickets to {TICKETS_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving tickets cache: {e}")

    logger.succeed(f"Generated {len(generated_tickets)} tickets")


async def seed_tickets():
    """
    Read tickets from cache file and insert them into Frappe helpdesk.
    """
    logger.start("Seeding tickets...")

    # Load tickets from cache
    if not TICKETS_CACHE_FILE.exists():
        logger.fail("Tickets cache file not found. Please run generate_tickets first.")
        return

    try:
        with TICKETS_CACHE_FILE.open() as f:
            cache_data = json.load(f)
            cached_tickets_data = cache_data.get("tickets", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading tickets cache: {e}")
        return

    if not cached_tickets_data:
        logger.fail("No tickets found in cache file")
        return

    successful_tickets = 0

    async def process_ticket(cached_ticket):
        nonlocal successful_tickets
        try:
            # Reconstruct objects from cached data
            ticket_data_dict = cached_ticket["ticket_data"]["ticket"]

            # Handle backwards compatibility for conversation_date field
            if "conversation_date" not in ticket_data_dict:
                # Generate a conversation date from the timestamp if available
                if ticket_data_dict.get("timestamp"):
                    conversation_date = datetime.fromtimestamp(ticket_data_dict["timestamp"]).strftime("%Y-%m-%d")
                    ticket_data_dict["conversation_date"] = conversation_date
                else:
                    # Fallback to a random date in the last 12 months
                    conversation_datetime = fake.date_time_between(start_date="-12M", end_date="now")
                    ticket_data_dict["conversation_date"] = conversation_datetime.strftime("%Y-%m-%d")

            # Handle backwards compatibility for rating field
            if "rating" not in ticket_data_dict:
                # Generate a realistic rating (1-5, distributed based on typical helpdesk outcomes)
                # Most tickets should have decent ratings (3-4) with some excellent (5) and poor (1-2)
                ticket_data_dict["rating"] = fake.choices(
                    elements=[1, 2, 3, 4, 5],
                    weights=[10, 15, 35, 30, 10],  # Weighted towards 3-4 ratings
                    length=1,
                )[0]

            # Handle backwards compatibility for conversation structure
            conversation_items = []
            cached_data = cached_ticket["ticket_data"]

            if "conversation" in cached_data:
                # New format: use conversation items directly
                conversation_items = [ConversationItem(**item) for item in cached_data["conversation"]]

                # Handle backwards compatibility for timestamp field
                if conversation_items and (not hasattr(conversation_items[0], "timestamp") or conversation_items[0].timestamp == 0.0):
                    # Generate timestamps for all items if missing (backwards compatibility)
                    ticket_creation_datetime = datetime.fromtimestamp(ticket_data_dict.get("timestamp", datetime.now().timestamp()))
                    generate_realistic_timestamps(conversation_items, ticket_creation_datetime)
            else:
                # Old format: convert comments and replies to conversation items
                sequence = 1

                # Add comments as conversation items
                if "comments" in cached_data:
                    for comment in cached_data["comments"]:
                        conversation_items.append(
                            ConversationItem(
                                type="comment",
                                content=comment["content"],
                                author=comment["commented_by"],
                                sequence=sequence,
                            )
                        )
                        sequence += 1

                # Add replies as conversation items (all old replies were agent replies)
                if "replies" in cached_data:
                    for reply in cached_data["replies"]:
                        conversation_items.append(
                            ConversationItem(
                                type="reply",
                                content=reply["content"],
                                author=reply["replied_by"],
                                sequence=sequence,
                            )
                        )
                        sequence += 1

            ticket_data = TicketData(
                ticket=Ticket(**ticket_data_dict),
                conversation=conversation_items,
            )

            contact = cached_ticket["contact"]
            customer_name = cached_ticket["customer_name"]

            await insert_single_ticket(ticket_data, contact, customer_name)
            successful_tickets += 1
        except Exception as e:
            logger.warning(f"Error creating ticket from cache: {e}")
            print(e)
            print(traceback.format_exc())

    # Create tasks for all tickets and run them concurrently
    semaphore = asyncio.Semaphore(5)  # Limit concurrent operations for tickets

    async def process_with_semaphore(cached_ticket):
        async with semaphore:
            await process_ticket(cached_ticket)

    tasks = [process_with_semaphore(cached_ticket) for cached_ticket in cached_tickets_data]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.succeed(f"Seeded {successful_tickets}/{len(cached_tickets_data)} tickets")
