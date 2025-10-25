import asyncio
import json
import random
from datetime import timedelta
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.chatwoot.config.settings import settings
from apps.chatwoot.core.agents import ADMIN_AGENT
from apps.chatwoot.core.contacts import get_all_contacts
from apps.chatwoot.utils.chatwoot import ChatwootClient
from apps.chatwoot.utils.database import AsyncPostgresClient
from apps.chatwoot.utils.faker import faker
from common.logger import logger


# Constants
CONVERSATION_DATA_FILE = Path(__file__).parent.parent.joinpath("data", "generated", "conversations.json")
MAX_CONCURRENT_CONVERSATIONS = 32
THREAD_LENGTH_MIN = 6
THREAD_LENGTH_MAX = 30
MESSAGE_DELAY = 0.1
CONVERSATION_GENERATION_DELAY = 0.1
MESSAGE_STATUS_FIX_RUNS = 2
MAX_PAGINATION_COUNT = 999


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class Message(BaseModel):
    type: Literal["incoming", "outgoing"] = Field(description="The indicator of the sender of the message (incoming or outgoing)")  # noqa: A003, RUF100
    content: str = Field(description="The content of the message, use markdown to format the message")


class MessageThread(BaseModel):
    thread: list[Message]
    priority: Literal["low", "medium", "high", "urgent"] = Field(description="The priority of the conversation")
    resolved: bool = Field(description="Whether the conversation is resolved", default=True)
    feedback: str | None = Field(
        description="The feedback of the conversation from the customer, only availabe if the conversation is resolved",
        default=None,
    )


class MessageThreadWithMetadata(MessageThread):
    labels: list[str] = Field(description="The label titles of the conversation")
    team_name: str = Field(description="The name of the team that the conversation belongs to")
    contact_email: str = Field(description="The email of the contact associated with the conversation")
    inbox_name: str = Field(description="The name of the inbox where the conversation takes place")
    agent_email: str = Field(description="The email of the agent assigned to the conversation")
    rating: int = Field(
        description="The rating of the conversation from the customer from 1 to 5",
        default=5,
    )


def _get_conversation_prompt(
    contact,
    inbox,
    agent,
    thread_length,
    labels,
    rating,
    resolved: bool,
    team: dict,
):
    """Generate the OpenAI prompt for conversation creation."""
    # Handle both API response format (channel_type) and generated JSON format (channel.type)
    channel_type = inbox.get("channel_type", "email")
    if channel_type == "email" and "channel" in inbox:
        channel_type = inbox["channel"].get("type", "email")

    return f"""Generate a realistic customer service conversation for Chatwoot between a customer and an agent.

CONTEXT:
- Company: {settings.COMPANY_NAME}
- Customer: {contact}
- Inbox: {inbox}
- Agent: {agent}
- Required length: {thread_length} messages
- Channel type: {channel_type}
- Conversation has to be assigned to team: {team}

CONVERSATION REQUIREMENTS:
1. Create a conversation appropriate for the {channel_type} channel
2. Focus on a specific customer issue or request with clear resolution
3. Use natural, realistic language without placeholders like [Customer Name] or [Your Name] or [Link here] etc.
4. This conversation should be related to the following labels: {labels}
5. The conversation should be {"resolved" if resolved else "pending"} in the end.
6. The conversation should have a rating and feedback from the customer. 
    -In their feedback, do not include anything else than the feedback in customer's POV, do not include phrases like "1 out of 5".
7. The customer will rate this conversation {rating} out of 5.
8. The content of the conversation should reflect the feedback of the customer. 

MESSAGE TYPES - FOLLOW EXACTLY:
- Customer messages: type="incoming", private_note=false
- Agent responses to customer: type="outgoing", private_note=false  
- Agent internal notes: type="outgoing", private_note=true

PRIVATE NOTES RULES:
- Include 1-3 internal agent notes throughout the conversation
- Private notes are agent's thoughts/notes for the team (not visible to customer)
- Examples of private note content:
  * "Customer seems frustrated, escalating to supervisor"
  * "Checked account - payment processed successfully"
  * "Following up on previous ticket #12345"
  * "Need to coordinate with billing team"
- Write private notes naturally as internal communication
- Every private note must start with "NOTE:", this must be placed in the beginning of the message content.
- Messages that are meant for the customer must not include "NOTE:"
- Conversation that are emails, private notes should not be included in email sent to customer, they should be sent as a separate message.

CONVERSATION FLOW:
1. Customer initiates with a problem/question
2. Agent responds (may include private note about initial assessment)
3. Continue back-and-forth with realistic problem-solving
4. Include private notes at natural points (after complex issues, before escalation, etc.)
5. End with resolution or next steps"""


async def _load_conversations_from_file(
    number_of_conversations: int | None = None,
) -> list[MessageThreadWithMetadata] | None:
    """Load conversations from the data file if it exists."""
    try:
        with CONVERSATION_DATA_FILE.open(encoding="utf-8") as f:
            conversations = [MessageThreadWithMetadata(**conversation) for conversation in json.load(f)]

            # Warn if the number of conversations in file differs from requested
            if number_of_conversations is not None and len(conversations) != number_of_conversations:
                logger.warning(
                    f"Number of conversations in file ({len(conversations)}) differs from requested ({number_of_conversations}). Using {len(conversations)} conversations from file."
                )

            return conversations

    except FileNotFoundError:
        logger.error(f"Conversations file not found: {CONVERSATION_DATA_FILE}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {CONVERSATION_DATA_FILE}")
        return None


async def _save_conversations_to_file(conversations: list[MessageThreadWithMetadata]):
    """Save conversations to the data file."""
    with CONVERSATION_DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump([conversation.model_dump() for conversation in conversations], f)


async def _create_conversation_with_ai(contact, agent, inbox, labels: list[dict], team: dict, index: int = 1) -> MessageThreadWithMetadata:
    """Create a single conversation using OpenAI."""
    await asyncio.sleep(CONVERSATION_GENERATION_DELAY * index)

    # Handle both API response format (channel_type) and generated JSON format (channel.type)
    channel_type = inbox.get("channel_type", "email")
    if channel_type == "email" and "channel" in inbox:
        channel_type = inbox["channel"].get("type", "email")

    rating = random.choices([1, 2, 3, 4, 5], weights=[1, 1, 3, 3, 2], k=1)[0]
    resolved = random.choices([True, False], weights=[85, 15], k=1)[0]
    thread_length = faker.random_int(min=THREAD_LENGTH_MIN, max=THREAD_LENGTH_MAX)
    prompt = _get_conversation_prompt(contact, inbox, agent, thread_length, labels, rating, resolved, team)

    thread = await openai_client.beta.chat.completions.parse(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that generates realistic data for Chatwoot",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format=MessageThread,
    )

    parsed = thread.choices[0].message.parsed

    return MessageThreadWithMetadata(
        contact_email=contact["email"],
        inbox_name=inbox["name"],
        thread=parsed.thread,
        team_name=team["name"],
        priority=parsed.priority,
        agent_email=agent["email"],
        resolved=parsed.resolved,
        labels=labels,
        feedback=parsed.feedback,
        rating=rating,
    )


async def _generate_conversations(number_of_conversations: int, agents, contacts, inboxes, labels, teams) -> list[MessageThreadWithMetadata]:
    """Generate conversations using AI concurrently."""

    # Create all conversation generation tasks
    tasks = []
    for i in range(number_of_conversations):
        contact = faker.random_element(contacts)
        inbox = faker.random_element(inboxes)

        # First select a team, then select an agent from that team's members
        # This ensures realistic team-agent assignments that match teams.json
        team = faker.random_element(teams)

        # Get an agent from the selected team's member emails
        agent = None
        if team.get("member_emails"):
            selected_agent_email = faker.random_element(team["member_emails"])
            # Use the improved agent finding function
            agent = _find_agent_by_email(agents, selected_agent_email)

            if not agent:
                # Try other team members before falling back to random
                for email in team["member_emails"]:
                    if email != selected_agent_email:
                        agent = _find_agent_by_email(agents, email)
                        if agent:
                            break

        # If still no agent found, use random fallback
        if not agent:
            agent = faker.random_element(agents)

        selected_labels = faker.random_elements(
            elements=[label["title"] for label in labels],  # Extract just the titles
            length=faker.random_int(min=1, max=3),
            unique=True,
        )

        task = _create_conversation_with_ai_with_retry(contact, agent, inbox, selected_labels, team, i)
        tasks.append(task)

    # Run all conversation generation tasks concurrently
    logger.info(f"Running {len(tasks)} conversation generation tasks concurrently...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out None results and exceptions to get successfully generated conversations
    successful_conversations = []
    failed_count = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Conversation {i + 1} failed with exception: {result}")
            failed_count += 1
        elif result is not None:
            successful_conversations.append(result)
            logger.info(f"Successfully generated conversation {i + 1}/{number_of_conversations}")
        else:
            logger.warning(f"Conversation {i + 1} returned None")
            failed_count += 1

    logger.info(f"Concurrent generation completed: {len(successful_conversations)} successful, {failed_count} failed")

    if successful_conversations:
        await _save_conversations_to_file(successful_conversations)

    return successful_conversations


async def _create_conversation_with_ai_with_retry(contact, agent, inbox, labels: list[dict], team: dict, index: int = 1) -> MessageThreadWithMetadata | None:
    """Create a single conversation with retry logic."""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            conversation = await _create_conversation_with_ai(contact, agent, inbox, labels, team, index)
            if conversation:
                return conversation
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for conversation {index + 1}: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate conversation {index + 1} after {max_retries} attempts")

    return None


def _find_agent_by_email(agents, email: str):
    """Find an agent by email address with robust matching and fallbacks."""
    try:
        # Try exact match first
        return next(a for a in agents if a["email"] == email)
    except StopIteration:
        # Try case-insensitive match
        try:
            return next(a for a in agents if a["email"].lower() == email.lower())
        except StopIteration:
            # Try finding by name if email doesn't match (common with generated vs real data)
            try:
                # Extract name from email for fuzzy matching
                email_name = email.split("@")[0].replace(".", " ").replace("_", " ")
                return next(a for a in agents if email_name.lower() in a.get("name", "").lower())
            except StopIteration:
                logger.warning(f"Agent not found: {email}")
                return None


def _find_contact_by_email(contacts, email: str):
    """Find a contact by email address."""
    try:
        return next(c for c in contacts if c["email"] == email)
    except StopIteration:
        logger.error(f"Contact with email {email} not found.")
        return None


async def _create_conversation_in_chatwoot(client, superadmin_client, inbox_id: int, contact_id: int, assignee_id: int, team_id: int | None = None):
    """Create a conversation in Chatwoot with fallback to superadmin client."""
    try:
        convo = await client.add_conversation(
            inbox_id=inbox_id,
            contact_id=contact_id,
            assignee_id=assignee_id,
        )

        # Assign to team immediately after creation if team_id is provided
        if team_id:
            try:
                await client.assign_conversation_to_team(convo["id"], team_id)

                # Check if team assignment changed the assignee
                check_query = "SELECT assignee_id FROM conversations WHERE id = $1"
                post_team_assignee = await AsyncPostgresClient.fetchval(check_query, convo["id"])
                if post_team_assignee != assignee_id:
                    # Restore the original assignee
                    restore_query = "UPDATE conversations SET assignee_id = $1 WHERE id = $2"
                    await AsyncPostgresClient.execute(restore_query, assignee_id, convo["id"])

            except Exception:
                try:
                    await superadmin_client.assign_conversation_to_team(convo["id"], team_id)

                    # Check if team assignment changed the assignee
                    check_query = "SELECT assignee_id FROM conversations WHERE id = $1"
                    post_team_assignee = await AsyncPostgresClient.fetchval(check_query, convo["id"])
                    if post_team_assignee != assignee_id:
                        # Restore the original assignee
                        restore_query = "UPDATE conversations SET assignee_id = $1 WHERE id = $2"
                        await AsyncPostgresClient.execute(restore_query, assignee_id, convo["id"])

                except Exception as e2:
                    logger.error(f"Failed to assign conversation to team: {e2}")

        return convo
    except Exception:
        try:
            convo = await superadmin_client.add_conversation(
                inbox_id=inbox_id,
                contact_id=contact_id,
                assignee_id=assignee_id,
            )

            # Assign to team immediately after creation if team_id is provided
            if team_id:
                try:
                    await superadmin_client.assign_conversation_to_team(convo["id"], team_id)

                    # Check if team assignment changed the assignee
                    check_query = "SELECT assignee_id FROM conversations WHERE id = $1"
                    post_team_assignee = await AsyncPostgresClient.fetchval(check_query, convo["id"])
                    if post_team_assignee != assignee_id:
                        # Restore the original assignee
                        restore_query = "UPDATE conversations SET assignee_id = $1 WHERE id = $2"
                        await AsyncPostgresClient.execute(restore_query, assignee_id, convo["id"])

                except Exception as e:
                    logger.error(f"Failed to assign conversation to team: {e}")

            return convo
        except Exception as e:
            logger.error(f"Error adding conversation: {e}")
            return None


async def _get_source_id_for_contact_inbox(contact_id: int, inbox_id: int) -> str | None:
    """Look up source_id from contact_inboxes table for given contact_id and inbox_id."""
    try:
        query = """
            SELECT source_id 
            FROM contact_inboxes 
            WHERE contact_id = $1 AND inbox_id = $2
            LIMIT 1
        """
        source_id = await AsyncPostgresClient.fetchval(query, contact_id, inbox_id)
        return source_id
    except Exception as e:
        logger.error(f"Error looking up source_id for contact_id {contact_id} and inbox_id {inbox_id}: {e}")
        return None


async def _add_message_to_conversation(
    conversation_id: int,
    message_content: str,
    message_type: str,
    private: bool,
    contact_id: int,
    agent_id: int,
    created_at,
    account_id: int = 1,
    inbox_id: int = 1,
) -> dict:
    """Add a message to a conversation by inserting directly into the database."""
    try:
        # Determine sender info based on message type
        if message_type == "incoming":
            db_message_type = 0
            sender_type = "Contact"
            sender_id = contact_id
        else:  # outgoing
            db_message_type = 1
            sender_type = "User"
            sender_id = agent_id

        # Look up source_id from contact_inboxes table
        source_id = await _get_source_id_for_contact_inbox(contact_id, inbox_id)

        insert_query = """
            INSERT INTO messages 
            (content, account_id, inbox_id, conversation_id, message_type, 
            created_at, updated_at, private, status, content_type, 
            content_attributes, sender_type, sender_id, external_source_ids,
            additional_attributes, processed_message_content, sentiment, source_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0, 0,
            NULL, $9, $10, '{}'::jsonb, '{}'::jsonb, $11, '{}'::jsonb, $12)
            RETURNING id
        """

        message_id = await AsyncPostgresClient.fetchval(
            insert_query,
            message_content,  # $1 - content
            account_id,  # $2 - account_id
            inbox_id,  # $3 - inbox_id
            conversation_id,  # $4 - conversation_id
            db_message_type,  # $5 - message_type (0=incoming, 1=outgoing)
            created_at,  # $6 - created_at
            created_at,  # $7 - updated_at (same as created_at)
            private,  # $8 - private
            sender_type,  # $9 - sender_type
            sender_id,  # $10 - sender_id
            message_content,  # $11 - processed_message_content
            source_id,  # $12 - source_id
        )

        return {"id": message_id}

    except Exception as e:
        logger.error(f"Error inserting message into database: {e}")
        raise


async def _add_labels_and_priority(client, superadmin_client, conversation_id: int, labels: list[str], priority: str):
    """Add labels and priority to a conversation with fallback to superadmin client."""
    try:
        await client.add_conversation_labels(
            conversation_id=conversation_id,
            labels=labels,
        )
    except Exception:
        await superadmin_client.add_conversation_labels(
            conversation_id=conversation_id,
            labels=labels,
        )

    try:
        await client.set_conversation_priority(
            conversation_id=conversation_id,
            priority=priority,
        )
    except Exception:
        await superadmin_client.set_conversation_priority(
            conversation_id=conversation_id,
            priority=priority,
        )


async def _process_conversation_messages(
    client,
    superadmin_client,
    conversation_id: int,
    conversation: MessageThreadWithMetadata,
    selected_labels: list[str],
    contact_id: int,
    agent_id: int,
    inbox_id: int,
):
    """Process all messages in a conversation thread."""
    thread = conversation.thread
    selected_priority = conversation.priority

    # Generate conversation start time within the past year
    conversation_start = faker.date_time_between(start_date="-1y", end_date="now")
    current_time = conversation_start

    for count, message in enumerate(thread):
        try:
            # Handle private notes
            message_content = message.content
            private = False
            if "NOTE:" in message_content:
                private = True
                message_content = message_content.replace("NOTE: ", "")

            # Generate realistic delay between messages (2 minutes to 4 hours)
            if count > 0:
                delay_minutes = faker.random_int(min=2, max=240)  # 2 minutes to 4 hours
                current_time = current_time + timedelta(minutes=delay_minutes)

            await _add_message_to_conversation(
                conversation_id,
                message_content,
                message.type,
                private,
                contact_id,
                agent_id,
                created_at=current_time,
                account_id=1,
                inbox_id=inbox_id,
            )

            # Small delay between messages to maintain natural flow and avoid API rate limits
            if count < len(thread) - 1:  # Don't delay after the last message
                await asyncio.sleep(MESSAGE_DELAY)

            # Add labels and priority only for the first message
            if count == 0:
                await _add_labels_and_priority(
                    client,
                    superadmin_client,
                    conversation_id,
                    selected_labels,
                    selected_priority,
                )

        except Exception as e:
            logger.error(f"Error adding message {count + 1} to conversation: {e}")


async def _add_csat_survey_response(
    conversation_id: int,
    rating: int,
    feedback_message: str,
    contact_id: int,
    agent_id: int,
    message_id: int,
    account_id: int = 1,
):
    """Add CSAT survey response to a conversation."""
    try:
        insert_query = """
            INSERT INTO csat_survey_responses 
            (account_id, conversation_id, message_id, rating, feedback_message, contact_id, assigned_agent_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
        """

        await AsyncPostgresClient.execute(
            insert_query,
            account_id,
            conversation_id,
            message_id,
            rating,
            feedback_message,
            contact_id,
            agent_id,
        )

    except Exception as e:
        logger.error(f"Error adding CSAT survey response for conversation {conversation_id}: {e}")


async def _send_feeback_message(
    conversation_id: int,
    rating: int,
    feedback_message: str,
    contact_id: int,
    display_type: str = "emoji",
    account_id: int = 1,
    inbox_id: int = 1,
):
    """Add feedback message to a conversation."""
    try:
        # Look up source_id from contact_inboxes table
        source_id = await _get_source_id_for_contact_inbox(contact_id, inbox_id)

        # Get the timestamp of the last message in this conversation to make CSAT timing realistic
        last_message_query = """
            SELECT created_at 
            FROM messages 
            WHERE conversation_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
        """
        last_message_time = await AsyncPostgresClient.fetchval(last_message_query, conversation_id)

        if last_message_time:
            # CSAT message should come 2-30 minutes after the last message using faker for realistic timing
            from datetime import timedelta

            # Use faker to generate realistic delay - typically customers respond within 5-45 minutes
            delay_minutes = faker.random_int(min=5, max=45)
            csat_created_at = last_message_time + timedelta(minutes=delay_minutes)
            # CSAT updated time is usually just a few seconds after creation (when customer submits)
            update_delay_seconds = faker.random_int(min=1, max=30)
            csat_updated_at = csat_created_at + timedelta(seconds=update_delay_seconds)
        else:
            # Fallback: create realistic timestamps using faker relative to conversation flow
            csat_created_at = faker.date_time_between(start_date="-30d", end_date="now")
            csat_updated_at = faker.date_time_between(start_date=csat_created_at, end_date="now")

        content = "Please rate the conversation"

        # Sanitize feedback_message to prevent JSON parsing errors
        if feedback_message:
            # Remove or replace problematic characters that could break JSON
            feedback_message = feedback_message.replace("\n", " ").replace("\r", " ")
            # Limit length to prevent overly long feedback
            feedback_message = feedback_message[:500] if len(feedback_message) > 500 else feedback_message
            # Strip leading/trailing whitespace
            feedback_message = feedback_message.strip()
        else:
            feedback_message = ""

        # Create content_attributes with CSAT data
        content_attributes = {"display_type": display_type, "submitted_values": {"csat_survey_response": {"feedback_message": feedback_message, "rating": rating}}}

        message_query = """
            INSERT INTO messages 
            (content, account_id, inbox_id, conversation_id, message_type, 
            created_at, updated_at, private, status, content_type, content_attributes,
            sender_type, sender_id, external_source_ids, additional_attributes,
            processed_message_content, sentiment, source_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, false, 2, 9, $8,
            NULL, NULL, '{}'::jsonb, '{}'::jsonb, $9, '{}'::jsonb, $10)
        """
        await AsyncPostgresClient.execute(
            message_query,
            content,  # $1 - content
            account_id,  # $2 - account_id
            inbox_id,  # $3 - inbox_id
            conversation_id,  # $4 - conversation_id
            3,  # $5 - message_type (3 for feedback)
            csat_created_at,  # $6 - realistic created_at timestamp
            csat_updated_at,  # $7 - realistic updated_at timestamp
            json.dumps(json.dumps(content_attributes, separators=(",", ":"))),  # $8 - double-encoded JSON string with escaped quotes
            content,  # $9 - processed_message_content
            source_id,  # $10 - source_id from contact_inboxes
        )

    except Exception as e:
        logger.error(f"Error adding feedback message for conversation {conversation_id}: {e}")


async def _get_inbox_csat_config(inbox_id: int) -> dict:
    """Get CSAT configuration for an inbox."""
    try:
        query = """
            SELECT csat_survey_enabled, csat_config 
            FROM inboxes 
            WHERE id = $1
        """
        result = await AsyncPostgresClient.fetchrow(query, inbox_id)

        if result and result["csat_config"]:
            # Parse the JSON config if it exists
            csat_config = json.loads(result["csat_config"]) if isinstance(result["csat_config"], str) else result["csat_config"]

            return {
                "enabled": result["csat_survey_enabled"],
                "display_type": csat_config.get("display_type", "emoji"),
                "message": csat_config.get("message", ""),
            }

        # Default configuration if no CSAT config found
        return {
            "enabled": False,
            "display_type": "emoji",
            "message": "",
        }
    except Exception as e:
        logger.error(f"Error getting CSAT config for inbox {inbox_id}: {e}")
        return {
            "enabled": False,
            "display_type": "emoji",
            "message": "",
        }


async def _process_single_conversation(
    conversation: MessageThreadWithMetadata,
    superadmin_client,
    agents,
    contacts,
    team_name_to_id,
    inbox_name_to_id,
    team_name_to_id_lower,
    inbox_name_to_id_lower,
    label_title_to_id,
    label_title_to_id_lower,
):
    """Process a single conversation and all its messages."""
    agent = _find_agent_by_email(agents, conversation.agent_email)
    if not agent:
        # Try to find any available agent as fallback
        if agents:
            agent = agents[0]  # Use first available agent
        else:
            logger.error("No agents available for fallback assignment. Skipping conversation.")
            return

    contact = _find_contact_by_email(contacts, conversation.contact_email)
    if not contact:
        logger.error(f"Skipping conversation - contact not found: {conversation.contact_email}")
        return

    # Try exact match first
    team_id = team_name_to_id.get(conversation.team_name)
    if not team_id:
        # Try case-insensitive match
        team_id = team_name_to_id_lower.get(conversation.team_name.lower())
    if not team_id:
        # Try with stripped whitespace
        team_id = team_name_to_id.get(conversation.team_name.strip())
    if not team_id:
        logger.error(f"Skipping conversation - team not found: '{conversation.team_name}'. Available teams: {list(team_name_to_id.keys())}")
        return

    # Try exact match first
    inbox_id = inbox_name_to_id.get(conversation.inbox_name)
    if not inbox_id:
        # Try case-insensitive match
        inbox_id = inbox_name_to_id_lower.get(conversation.inbox_name.lower())
    if not inbox_id:
        # Try with stripped whitespace
        inbox_id = inbox_name_to_id.get(conversation.inbox_name.strip())
    if not inbox_id:
        logger.error(f"Skipping conversation - inbox not found: '{conversation.inbox_name}'. Available inboxes: {list(inbox_name_to_id.keys())}")
        return

    # Get CSAT configuration for the inbox
    csat_config = await _get_inbox_csat_config(inbox_id)

    async with ChatwootClient(email=agent["email"]) as client:
        convo = await _create_conversation_in_chatwoot(client, superadmin_client, inbox_id, contact["id"], agent["id"], team_id)

        if not convo:
            logger.error("Failed to create conversation, skipping...")
            return

        # Process labels with robust lookup
        selected_labels = []
        for label_title in conversation.labels:
            # Try exact match first
            label_id = label_title_to_id.get(label_title)
            if not label_id:
                # Try case-insensitive match
                label_id = label_title_to_id_lower.get(label_title.lower())
            if not label_id:
                # Try with stripped whitespace
                label_id = label_title_to_id.get(label_title.strip())

            if label_id:
                selected_labels.append(label_title)  # Keep using title for API compatibility

        await _process_conversation_messages(
            client,
            superadmin_client,
            convo["id"],
            conversation,
            selected_labels,
            contact_id=contact["id"],
            agent_id=agent["id"],
            inbox_id=inbox_id,
        )

        # Ensure assignee matches message sender
        verify_query = "SELECT assignee_id FROM conversations WHERE id = $1"
        final_assignee_id = await AsyncPostgresClient.fetchval(verify_query, convo["id"])

        if final_assignee_id != agent["id"]:
            # Fix the assignment
            try:
                fix_query = "UPDATE conversations SET assignee_id = $1 WHERE id = $2"
                await AsyncPostgresClient.execute(fix_query, agent["id"], convo["id"])
            except Exception as e:
                logger.error(f"Failed to fix assignee: {e}")

        if conversation.resolved:
            try:
                await superadmin_client.set_conversation_status(convo["id"], "resolved", snoozed_until=None)
                await _send_feeback_message(
                    conversation_id=convo["id"],
                    rating=conversation.rating,
                    feedback_message=conversation.feedback,
                    contact_id=contact["id"],
                    display_type=csat_config["display_type"],
                    account_id=1,  # Using default account_id
                    inbox_id=inbox_id,
                )
            except Exception as e:
                logger.error(f"Error resolving conversation: {e}")

        if conversation.feedback and conversation.rating and random.random() < 0.6:
            await _add_csat_survey_response(
                conversation_id=convo["id"],
                rating=conversation.rating,
                feedback_message=conversation.feedback,
                contact_id=contact["id"],
                agent_id=agent["id"],
                message_id=convo["id"],
            )

        logger.debug(f"Seeded conversation {convo['id']}")


async def generate_conversations(number_of_conversations: int):
    """Generate specified number of conversations and save them to JSON file."""
    # Ensure the generated directory exists
    CONVERSATION_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load data from JSON files instead of Chatwoot
    logger.info("Loading data from JSON files...")

    # Load agents from generated file
    agents_file = settings.DATA_PATH / "generated" / "agents.json"
    try:
        with agents_file.open(encoding="utf-8") as f:
            agents = json.load(f)
            # Add fake IDs if missing (for generation compatibility)
            for i, agent in enumerate(agents):
                if "id" not in agent:
                    agent["id"] = i + 1
            logger.info(f"Loaded {len(agents)} agents from {agents_file}")
            agents.append(ADMIN_AGENT)  # Ensure admin agent is always included
    except FileNotFoundError:
        logger.error(f"Agents file not found: {agents_file}")
        logger.error("Please run generate_agents() first to create the agents file")
        return

    # Load contacts from generated file
    contacts_file = settings.DATA_PATH / "generated" / "contacts.json"
    try:
        with contacts_file.open(encoding="utf-8") as f:
            contacts = json.load(f)
            # Add fake IDs if missing (for generation compatibility)
            for i, contact in enumerate(contacts):
                if "id" not in contact:
                    contact["id"] = i + 1
            logger.info(f"Loaded {len(contacts)} contacts from {contacts_file}")
    except FileNotFoundError:
        logger.error(f"Contacts file not found: {contacts_file}")
        logger.error("Please run generate_contacts() first to create the contacts file")
        return

    # Load inboxes from generated file
    inboxes_file = settings.DATA_PATH / "generated" / "inboxes.json"
    try:
        with inboxes_file.open(encoding="utf-8") as f:
            inboxes = json.load(f)
            # Add fake IDs if missing (for generation compatibility)
            for i, inbox in enumerate(inboxes):
                if "id" not in inbox:
                    inbox["id"] = i + 1
            logger.info(f"Loaded {len(inboxes)} inboxes from {inboxes_file}")
    except FileNotFoundError:
        logger.error(f"Inboxes file not found: {inboxes_file}")
        logger.error("Please run generate_inboxes() first to create the inboxes file")
        return

    # Load labels from generated file
    labels_file = settings.DATA_PATH / "generated" / "labels.json"
    try:
        with labels_file.open(encoding="utf-8") as f:
            labels = json.load(f)
            # Add fake IDs if missing (for generation compatibility)
            for i, label in enumerate(labels):
                if "id" not in label:
                    label["id"] = i + 1
            logger.info(f"Loaded {len(labels)} labels from {labels_file}")
    except FileNotFoundError:
        logger.error(f"Labels file not found: {labels_file}")
        logger.error("Please run generate_labels() first to create the labels file")
        return

    # Load teams from generated file
    teams_file = settings.DATA_PATH / "generated" / "teams.json"
    try:
        with teams_file.open(encoding="utf-8") as f:
            teams = json.load(f)
            # Add fake IDs if missing (for generation compatibility)
            for i, team in enumerate(teams):
                if "id" not in team:
                    team["id"] = i + 1
            logger.info(f"Loaded {len(teams)} teams from {teams_file}")
    except FileNotFoundError:
        logger.error(f"Teams file not found: {teams_file}")
        logger.error("Please run generate_teams() first to create the teams file")
        return

    await _generate_conversations(number_of_conversations, agents, contacts, inboxes, labels, teams)


async def seed_conversations():
    """Seed conversations from JSON file into Chatwoot."""
    # Try to load conversations from file
    conversations = await _load_conversations_from_file()

    if conversations is None:
        logger.error(f"Conversations file not found: {CONVERSATION_DATA_FILE}")
        logger.error("Please run generate_conversations() first to create the conversations file")
        return

    async with ChatwootClient() as superadmin_client:
        # Get current data from Chatwoot to look up IDs
        agents = await superadmin_client.list_agents()
        contacts = await get_all_contacts()

        logger.info(f"Loaded {len(agents)} agents and {len(contacts)} contacts from Chatwoot")

        # Get teams and inboxes from database instead of API
        teams_query = "SELECT id, name FROM teams WHERE account_id = $1"
        teams_data = await AsyncPostgresClient.fetch(teams_query, int(settings.DEFAULT_ACCOUNT_ID))
        teams = [{"id": team["id"], "name": team["name"]} for team in teams_data]

        inboxes_query = "SELECT id, name FROM inboxes WHERE account_id = $1"
        inboxes_data = await AsyncPostgresClient.fetch(inboxes_query, int(settings.DEFAULT_ACCOUNT_ID))
        inboxes = [{"id": inbox["id"], "name": inbox["name"]} for inbox in inboxes_data]

        labels_query = "SELECT id, title FROM labels WHERE account_id = $1"
        labels_data = await AsyncPostgresClient.fetch(labels_query, int(settings.DEFAULT_ACCOUNT_ID))
        labels = [{"id": label["id"], "title": label["title"]} for label in labels_data]

        logger.info(f"Loaded {len(teams)} teams, {len(inboxes)} inboxes, {len(labels)} labels")

        # Create lookup dictionaries for names to IDs
        team_name_to_id = {team["name"].strip(): team["id"] for team in teams}
        inbox_name_to_id = {inbox["name"].strip(): inbox["id"] for inbox in inboxes}
        label_title_to_id = {label["title"].strip(): label["id"] for label in labels}

        # Also create case-insensitive lookups for better matching
        team_name_to_id_lower = {team["name"].strip().lower(): team["id"] for team in teams}
        inbox_name_to_id_lower = {inbox["name"].strip().lower(): inbox["id"] for inbox in inboxes}
        label_title_to_id_lower = {label["title"].strip().lower(): label["id"] for label in labels}

        # Process all conversations in parallel with concurrency control
        logger.start(f"Seeding {len(conversations)} conversations...")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONVERSATIONS)

        async def process_with_semaphore(conversation):
            async with semaphore:
                await _process_single_conversation(
                    conversation,
                    superadmin_client,
                    agents,
                    contacts,
                    team_name_to_id,
                    inbox_name_to_id,
                    team_name_to_id_lower,
                    inbox_name_to_id_lower,
                    label_title_to_id,
                    label_title_to_id_lower,
                )

        conversation_tasks = [process_with_semaphore(conversation) for conversation in conversations]

        await asyncio.gather(*conversation_tasks)

        logger.info(f"Completed seeding {len(conversations)} conversations")


async def insert_conversations(number_of_conversations: int):
    """Legacy function - generates conversations and seeds them into Chatwoot."""
    await generate_conversations(number_of_conversations)
    await seed_conversations()


async def resolve_conversations():
    """Resolve a random selection of conversations."""
    async with ChatwootClient() as client:
        conversations = await get_all_conversations()
        logger.info(f"Found {len(conversations)} conversations")

        for conversation in conversations:
            try:
                await client.set_conversation_status(conversation["id"], "resolved", snoozed_until=None)
            except Exception as e:
                logger.error(f"Error resolving conversation: {e}")


async def _fix_message_status_single_run(run_number: int):
    """Execute a single run of message status fixing."""

    try:
        # Get all messages where status = 3
        query = "SELECT * FROM messages WHERE status = $1"
        messages = await AsyncPostgresClient.fetch(query, 3)
        logger.info(f"Found {len(messages)} messages with status = 3")

        if messages:
            update_query = "UPDATE messages SET status = $1 WHERE status = $2"
            await AsyncPostgresClient.execute(update_query, 0, 3)

        # Delete messages where content_attributes contains "error"
        delete_error_query = "DELETE FROM messages WHERE content_attributes::text LIKE '%error%'"
        await AsyncPostgresClient.execute(delete_error_query)

    except Exception as e:
        logger.error(f"Error updating message statuses in run {run_number}: {e}")


async def fix_message_status():
    """Fix message statuses by updating status=3 to status=0 and clearing content_attributes."""
    logger.info("Fixing message statuses...")

    # Run the fix multiple times with delay between runs
    for run_number in range(1, MESSAGE_STATUS_FIX_RUNS + 1):
        await _fix_message_status_single_run(run_number)

    logger.info("Completed all message status fix runs")
    return []


async def get_all_conversations(max_conversations: int | None = None):
    """Retrieve all conversations with optional limit."""
    async with ChatwootClient() as client:
        all_conversations = []
        page = 1
        count = 0

        while count < MAX_PAGINATION_COUNT:
            conversations = await client.list_conversations(page)

            if not conversations:  # No more conversations to fetch
                break

            all_conversations.extend(conversations)

            # Check if we've reached the maximum requested conversations
            if max_conversations is not None and len(all_conversations) >= max_conversations:
                all_conversations = all_conversations[:max_conversations]
                break

            page += 1
            count += 1

        return all_conversations
