import asyncio
import datetime
import random
import time

from apps.mattermost.config.settings import settings
from apps.mattermost.core.message import update_post_timestamp
from apps.mattermost.core.messages import (
    convert_llm_to_complete_messages,
    create_attachment_instructions,
    create_base_post_data,
    create_business_theme_context,
    create_markdown_guidelines,
    create_timestamp_context,
    create_user_directory_context,
    generate_conversation_timestamps,
    generate_thread_with_llm,
    handle_file_attachments,
    handle_message_pinning,
    handle_message_reactions,
    prepare_threads_for_json,
)
from apps.mattermost.models.message import (
    DirectMessages,
    Message,
    Thread,
)
from apps.mattermost.utils.constants import DM_MESSAGE_REACTION_PROBABILITY, THREAD_ATTACHMENT_PROBABILITY
from apps.mattermost.utils.database import AsyncPostgresClient
from apps.mattermost.utils.faker import faker
from apps.mattermost.utils.mattermost import MattermostClient
from common.load_json import load_json
from common.logger import logger
from common.save_to_json import save_to_json


DM_PATH = settings.DATA_PATH.joinpath("direct_messages.json")
USERS_PATH = settings.DATA_PATH.joinpath("users.json")


async def _update_dm_thread_metadata(root_post_id: str, last_reply_timestamp: int | None) -> None:
    """Update only the lastreplyat column in the threads table for direct messages."""
    try:
        # Use current timestamp if last_reply_timestamp is not provided
        if last_reply_timestamp is None:
            last_reply_timestamp = int(time.time() * 1000)

        # Only update lastreplyat column
        update_query = """
        UPDATE threads 
        SET lastreplyat = $1
        WHERE postid = $2
        """

        await AsyncPostgresClient.execute(update_query, last_reply_timestamp, root_post_id)

    except Exception as e:
        logger.warning(f"Failed to update DM thread lastreplyat for post {root_post_id}: {e}")


def _set_probabilistic_message_attributes(messages: list[Message], owner_id: int, member_id: int) -> list[Message]:
    """Set is_pinned, has_reactions, and from_user probabilistically for messages."""

    # Ensure we have valid and different user IDs
    if owner_id == member_id:
        logger.warning(f"Owner and member IDs are the same: {owner_id}. This will create unbalanced conversations.")

    if owner_id is None or member_id is None:
        logger.warning(f"Invalid user IDs: owner_id={owner_id}, member_id={member_id}")
        return messages

    # Create list of both users for fair selection
    users = [owner_id, member_id]

    # First message - randomly select from either user (50/50 chance)
    current_user = random.choice(users)

    for i, message in enumerate(messages):
        # Set is_pinned with 5% probability (lower than channels since DMs are more personal)
        message.is_pinned = random.random() < 0.05

        # Set has_reactions with configurable probability
        message.has_reactions = random.random() < (DM_MESSAGE_REACTION_PROBABILITY / 100)

        # Attachment filenames will be determined by LLM based on message content
        message.attachment_filenames = []

        # Assign from_user programmatically
        message.from_user = current_user

        # For next message, decide if we should switch users
        # 60% chance to switch to other user (creates natural conversation flow)
        if i < len(messages) - 1 and random.random() < 0.6:
            # Switch to the other user
            current_user = member_id if current_user == owner_id else owner_id

    return messages


def _create_message_context_prompt(messages: list[Message], owner: dict, member: dict) -> str:
    """Create context prompt with probabilistic message attributes and user context."""
    context_lines = []
    for i, message in enumerate(messages, 1):
        pin_status = "PINNED" if message.is_pinned else "not pinned"
        reaction_status = "MUST have reactions" if message.has_reactions else "optional reactions"
        attachment_status = "WITH file attachment" if message.attachment_filenames else "no attachment"

        # Determine who is speaking and who they're talking to
        if message.from_user == owner["id"]:
            speaker = f"{owner['username']} (speaking as the admin/owner)"
            listener = f"{member['username']}"
        else:
            speaker = f"{member['username']} (speaking as the team member)"
            listener = f"{owner['username']}"

        context_lines.append(f"Message {i}: {speaker} speaking TO {listener}, {pin_status}, {reaction_status}, {attachment_status}")

    return "\n".join(context_lines)


# Using shared timestamp generation from core/messages/timestamp_generation.py


async def _generate_dm_conversation(user1: dict, user2: dict, earliest_communication_date: int, all_users: list[dict], threads_per_dm_range: tuple[int, int]) -> list[Thread]:
    """Generate a 1-on-1 DM conversation with multiple threads between two users."""

    # Generate threads based on CLI parameters for 1-on-1 DMs
    min_threads, max_threads = threads_per_dm_range
    thread_count = random.randint(min_threads, max_threads)

    # Generate threads similar to group DM logic
    threads_with_attributes = []
    thread_timestamps = []

    for i in range(thread_count):
        # Generate thread message count using the messages_per_thread parameter as base
        thread_message_count = faker.random_int(min=3, max=8)  # 3-8 messages per thread

        # Generate realistic timestamps for this thread
        if i == 0:
            thread_start_time = earliest_communication_date
        else:
            # Subsequent threads start after previous thread with some gap
            gap_hours = random.randint(1, 48)  # 1-48 hours gap between threads
            thread_start_time = thread_timestamps[-1] + (gap_hours * 60 * 60 * 1000)

        thread_timestamps.append(thread_start_time)
        thread_message_timestamps = generate_conversation_timestamps(thread_message_count, thread_start_time)

        # Create empty message objects with probabilistic attributes and pre-generated timestamps
        messages_with_attributes = []
        for j in range(thread_message_count):
            message = Message(
                from_user=0,  # Will be set later
                content="",  # Will be filled by LLM
                timestamp=thread_message_timestamps[j],
            )
            messages_with_attributes.append(message)

        # Set probabilistic message attributes (but not user assignments - LLM strategy will handle that)
        for message in messages_with_attributes:
            # Set is_pinned with 5% probability (lower than channels since DMs are more personal)
            message.is_pinned = random.random() < 0.05
            # Set has_reactions with configurable probability
            message.has_reactions = random.random() < (DM_MESSAGE_REACTION_PROBABILITY / 100)
            # Attachment filenames will be determined by LLM based on message content
            message.attachment_filenames = []
            # Leave from_user as 0 so convert_llm_to_complete_messages will use the strategy

        # Create thread with probabilistic threading behavior (30% chance)
        thread = Thread(messages=messages_with_attributes, has_root_message=random.random() < 0.3)

        # Determine if this thread should have attachments
        thread.should_have_attachments = faker.boolean(chance_of_getting_true=THREAD_ATTACHMENT_PROBABILITY)

        threads_with_attributes.append(thread)

    # Now we need to create a helper function similar to _generate_single_thread_for_group
    # but specifically for 1-on-1 DMs. Let me implement the thread generation logic here:

    # Generate each thread separately for better focus and quality
    successful_threads = []
    total_messages = 0

    for i, thread_template in enumerate(threads_with_attributes):
        try:
            thread_message_count = len(thread_template.messages)
            thread_start_time = thread_timestamps[i]

            # Determine who is the owner and who is the member
            owner_username = settings.MATTERMOST_OWNER_USERNAME
            if user1["username"] == owner_username:
                owner, member = user1, user2
            else:
                owner, member = user2, user1

            # Create context for this specific thread
            _create_message_context_prompt(thread_template.messages, owner, member)

            # Create user directory for LLM context
            user_directory = []
            for user in all_users[:20]:  # Limit to first 20 users to avoid token limits
                user_entry = f"ID {user['id']}: {user['username']} ({user.get('position', 'Unknown Position')})"
                user_directory.append(user_entry)

            user_directory_text = "\n        ".join(user_directory)

            # Create timestamp context for the LLM
            thread_start_date = datetime.datetime.fromtimestamp(thread_start_time / 1000)

            timestamp_context = f"""
                **Thread Timeline:**
                - This thread started on {thread_start_date.strftime("%B %d, %Y at %I:%M %p")}
                - Generate content that would be appropriate for that time period
            """

            # Determine attachment instructions based on thread flag
            attachment_instruction = create_attachment_instructions(getattr(thread_template, "should_have_attachments", False))

            user_prompt = f"""
                Generate a single conversation thread for a 1-on-1 direct message between two users.
                Create exactly {thread_message_count} messages that form a cohesive conversation on one topic.
                {create_business_theme_context()}
                
                {timestamp_context}
                
                **Available Participants (choose from these for each message's from_user):**
                - User ID {owner["id"]}: {owner["username"]} - {owner.get("first_name", "")} {owner.get("last_name", "")} ({owner.get("position", "Owner/Admin")})
                - User ID {member["id"]}: {member["username"]} - {member.get("first_name", "")} {member.get("last_name", "")} ({member.get("position", "Team Member")})

                **User Directory (for realistic context and mentions):**
                {user_directory_text}
                
                **Mention Guidelines:**
                - When mentioning a user in the message, use @username format (e.g., @robert.jenkins)
                - Don't add any special characters around the username
                - Use mentions naturally when referring to the other person in direct messages
                
                {create_markdown_guidelines(is_team_channel=False)}
                {attachment_instruction}
                
                **Style:** Professional yet friendly DM between admin/owner and team member. The conversation should feel natural, supportive, and collaborative.
                
                **CRITICAL Instructions:**
                - Generate exactly 1 thread with exactly {thread_message_count} messages that form a focused conversation on a single topic
                - For each message, choose the appropriate from_user ID from the participants list above
                - Make the conversation flow naturally with realistic back-and-forth between the two users
                - Ensure the content matches who is speaking (don't have someone say "Hi John" if they ARE John)
            """

            response = await generate_thread_with_llm(user_prompt, context_type=f"1-on-1 DM between {user1['username']} and {user2['username']}")

            if not response:
                continue

            # Convert LLM messages to complete Message models using shared utility
            complete_messages = convert_llm_to_complete_messages(response, thread_template)

            # Create complete Thread with programmatic fields from template
            complete_thread = Thread(messages=complete_messages, has_root_message=thread_template.has_root_message)
            successful_threads.append(complete_thread)
            total_messages += len(complete_messages)

        except Exception as e:
            logger.warning(f"Failed to generate thread {i + 1} for 1-on-1 DM: {e}")
            continue

    logger.info(f"LLM generated {len(successful_threads)} conversation threads with {total_messages} total messages")
    return successful_threads


async def _generate_single_thread_for_group(group_users: list[dict], thread_message_count: int, thread_start_time: int, thread_template: Thread, all_users: list[dict]) -> Thread | None:
    """Generate a single conversation thread for a group DM with focused LLM call."""
    try:
        usernames = [user["username"] for user in group_users]

        # Create user context for LLM (participants in this group DM)
        user_context = []
        for user in group_users:
            user_context.append(
                f"- User ID {user['id']}: {user['username']} - {user.get('first_name', 'Unknown')} {user.get('last_name', 'Unknown')} ({user.get('position', 'Unknown Position')})"
            )

        user_context_str = "\n".join(user_context)

        # Create shared context using utilities
        user_directory_text = create_user_directory_context(all_users, limit=20)
        timestamp_context = create_timestamp_context(thread_start_time, "Conversation")
        attachment_instruction = create_attachment_instructions(getattr(thread_template, "should_have_attachments", False))

        # Create prompt for single thread
        user_prompt = f"""
        Generate a single conversation thread for a group direct message between {len(group_users)} users.
        Create exactly {thread_message_count} messages that form a cohesive conversation on one topic.
        {create_business_theme_context()}
        
        {timestamp_context}
        
        **Available Participants (choose from these for each message's from_user):**
        {user_context_str}

        **User Directory (for realistic context and mentions):**
        {user_directory_text}
        
        **Mention Guidelines:**
        - When mentioning a user in the message, use @username format (e.g., @robert.jenkins)
        - Don't add any special characters around the username
        - Use mentions naturally when asking questions or directing comments to specific participants
        
        {create_markdown_guidelines(is_team_channel=False)}
        {attachment_instruction}
        
        **Style:** Very casual, friendly, and personal group chat. Use informal language, occasional emojis (minimal usage), inside jokes, 
        personal references, supportive interactions, and warm camaraderie. Think of close friends chatting privately.
        
        **CRITICAL Instructions:**
        - Generate message thread with at least {thread_message_count} messages that form a focused conversation on a single topic
        - For each message, choose the appropriate from_user ID from the participants list above
        - Make the conversation flow naturally with realistic group chat dynamics
        - Ensure the content matches who is speaking (don't have someone refer to themselves in third person)
        """

        # Call LLM to generate single thread using shared utility
        response = await generate_thread_with_llm(user_prompt, context_type=f"group DM with users: {', '.join(usernames)}")

        if not response:
            return None

        # Convert LLM messages to complete Message models using shared utility
        complete_messages = convert_llm_to_complete_messages(response, thread_template)

        # Create complete Thread with programmatic fields from template
        complete_thread = Thread(messages=complete_messages, has_root_message=thread_template.has_root_message)

        return complete_thread

    except Exception as e:
        logger.error(f"Failed to generate single thread for group DM: {e}")
        return None


async def _generate_group_dm_conversation(
    group_users: list[dict], messages_per_thread: int, threads_per_dm_range: tuple[int, int], earliest_date: int, all_users: list[dict]
) -> list[Thread]:
    """Generate a group DM conversation with multiple threads between multiple users."""
    try:
        # Create context for group conversation
        usernames = [user["username"] for user in group_users]
        logger.info(f"Generating group DM conversation with {len(group_users)} users: {', '.join(usernames)}")

        # Generate threads based on CLI parameters for group DMs
        min_threads, max_threads = threads_per_dm_range
        thread_count = random.randint(min_threads, max_threads)

        # First, generate realistic timestamps for the threads
        thread_timestamps = generate_conversation_timestamps(thread_count, earliest_date)

        # Create thread templates with probabilistic attributes
        threads_with_attributes = []
        for i in range(thread_count):
            # Each thread gets a randomized number of messages based on the target
            # Use faker to add variation: ±50% of messages_per_thread, minimum 2
            min_messages = max(2, int(messages_per_thread * 0.5))
            max_messages = int(messages_per_thread * 1.5)
            thread_message_count = faker.random_int(min=min_messages, max=max_messages)

            # Generate timestamps for messages within this thread
            thread_start_time = thread_timestamps[i]
            message_timestamps = generate_conversation_timestamps(thread_message_count, thread_start_time)

            # Create messages for this thread
            thread_messages = []
            for j in range(thread_message_count):
                message = Message(
                    content="",  # Will be filled by LLM
                    from_user=0,  # Will be set based on LLM response
                    create_at=0,  # Will be calculated
                    is_pinned=random.random() < 0.05,  # 5% chance
                    has_reactions=random.random() < 0.15,  # 15% chance
                    timestamp=message_timestamps[j],  # Pre-generated timestamp
                )
                thread_messages.append(message)

            # Create thread with probabilistic has_root_message
            thread = Thread(
                messages=thread_messages,
                has_root_message=random.random() < 0.3,  # 30% chance for threading
            )

            # Determine if this thread should have attachments
            thread.should_have_attachments = faker.boolean(chance_of_getting_true=THREAD_ATTACHMENT_PROBABILITY)

            threads_with_attributes.append(thread)

        # Generate each thread separately for better focus and quality
        thread_tasks = []
        for i, thread_template in enumerate(threads_with_attributes):
            thread_message_count = len(thread_template.messages)
            thread_start_time = thread_timestamps[i]

            # Create task for generating this specific thread
            task = _generate_single_thread_for_group(group_users, thread_message_count, thread_start_time, thread_template, all_users)
            thread_tasks.append(task)

        # Execute all thread generations concurrently
        generated_threads = await asyncio.gather(*thread_tasks, return_exceptions=True)

        # Filter out failed threads and log results
        successful_threads = []
        total_messages = 0
        for i, thread_result in enumerate(generated_threads):
            if isinstance(thread_result, Exception):
                logger.warning(f"Failed to generate thread {i + 1} for group DM: {thread_result}")
                continue
            elif thread_result:
                successful_threads.append(thread_result)
                total_messages += len(thread_result.messages)

        if not successful_threads:
            logger.warning(f"No group DM threads generated for users: {', '.join(usernames)}")
            return []

        logger.info(f"LLM generated {len(successful_threads)} group conversation threads with {total_messages} total messages")
        return successful_threads

    except Exception as e:
        logger.error(f"Failed to generate group DM conversation for users {', '.join(usernames)}: {e}")
        return []


async def _generate_dm_batch(dm_groups_with_dates: list[tuple], messages_per_thread: int, threads_per_dm_range: tuple[int, int], all_users: list[dict]) -> list[DirectMessages]:
    """Generate a batch of DM conversations."""
    tasks = []
    for group_users, earliest_date in dm_groups_with_dates:
        if len(group_users) == 2:
            # 1-on-1 DM - use updated function (returns list[Thread])
            tasks.append(_generate_dm_conversation(group_users[0], group_users[1], earliest_date, all_users, threads_per_dm_range))
        else:
            # Group DM - use new function (returns list[Thread])
            tasks.append(_generate_group_dm_conversation(group_users, messages_per_thread, threads_per_dm_range, earliest_date, all_users))

    # Execute all conversations concurrently
    conversation_results = await asyncio.gather(*tasks, return_exceptions=True)

    dm_conversations = []
    for i, (group_users, _) in enumerate(dm_groups_with_dates):
        result = conversation_results[i]

        if isinstance(result, Exception):
            usernames = [u["username"] for u in group_users]
            logger.error(f"Failed to generate DM between {', '.join(usernames)}: {result}")
            continue

        if not result:
            usernames = [u["username"] for u in group_users]
            logger.warning(f"No messages generated for DM between {', '.join(usernames)}")
            continue

        # Create DirectMessages object using local integer IDs
        member_ids = [user["id"] for user in group_users]

        # Both 1-on-1 and group DMs now return list[Thread]
        dm_conversation = DirectMessages(members=member_ids, threads=result)

        dm_conversations.append(dm_conversation)

    return dm_conversations


def _find_common_teams(user1: dict, user2: dict) -> list[tuple[str, int]]:
    """Find common teams between two users and return earliest mutual join date for each team."""
    user1_teams = user1.get("team_channels", {})
    user2_teams = user2.get("team_channels", {})

    common_teams = []
    for team_name in user1_teams:
        if team_name in user2_teams:
            # Find the earliest date when both users were in any channel of this team
            user1_team_joins = [channel_info.get("joined_at", 0) for channel_info in user1_teams[team_name].values()]
            user2_team_joins = [channel_info.get("joined_at", 0) for channel_info in user2_teams[team_name].values()]

            if user1_team_joins and user2_team_joins:
                # The earliest mutual communication could happen after both users joined at least one channel
                earliest_user1 = min(user1_team_joins)
                earliest_user2 = min(user2_team_joins)
                mutual_earliest = max(earliest_user1, earliest_user2)  # Both must have joined
                common_teams.append((team_name, mutual_earliest))

    return common_teams


def _can_users_communicate(user1: dict, user2: dict) -> tuple[bool, int]:
    """Check if two users can communicate via DM and return the earliest possible communication date."""
    # Special case: MATTERMOST_OWNER_USERNAME can communicate with anyone who has joined any team
    owner_username = settings.MATTERMOST_OWNER_USERNAME

    if user1["username"] == owner_username or user2["username"] == owner_username:
        # Owner can talk to anyone - use the user's joined_at timestamp as communication start
        non_owner = user2 if user1["username"] == owner_username else user1

        # Use the user's general joined_at timestamp if available
        if "joined_at" in non_owner:
            return True, non_owner["joined_at"]

        # Fallback: check team_channels if joined_at not available
        non_owner_teams = non_owner.get("team_channels", {})
        if non_owner_teams:
            # Find the earliest team join date for the non-owner user
            all_join_dates = []
            for team_channels in non_owner_teams.values():
                for channel_info in team_channels.values():
                    if "joined_at" in channel_info:
                        all_join_dates.append(channel_info["joined_at"])

            if all_join_dates:
                earliest_join = min(all_join_dates)
                return True, earliest_join

        # Final fallback: allow communication with a default timestamp (30 days ago)
        import time

        thirty_days_ago = int((time.time() - (30 * 24 * 60 * 60)) * 1000)
        return True, thirty_days_ago

    # Regular users: must share at least one common team
    common_teams = _find_common_teams(user1, user2)

    if not common_teams:
        return False, 0

    # Return the earliest possible communication date (earliest common team join)
    earliest_communication = min(join_date for _, join_date in common_teams)
    return True, earliest_communication


async def generate_direct_messages(direct_message_channels: int, min_threads_per_dm: int = 4, max_threads_per_dm: int = 25):
    """Generate direct messages between users with concurrent processing and team membership validation."""
    logger.info(f"Generating {direct_message_channels} direct message conversations")

    # Load users data
    users_data = load_json(USERS_PATH)

    if len(users_data) < 2:
        logger.warning("Need at least 2 users to generate direct messages")
        return

    # Find the owner user first
    owner_user = None
    other_users = []

    for user in users_data:
        if user["username"] == settings.MATTERMOST_OWNER_USERNAME:
            owner_user = user
        else:
            other_users.append(user)

    if not owner_user:
        logger.warning(f"Owner user '{settings.MATTERMOST_OWNER_USERNAME}' not found in users data")
        return

    # We need enough users to create the requested number of conversations
    # For simplicity, let's ensure we have enough users (we'll reuse users if needed for group DMs)
    if direct_message_channels > len(other_users):
        logger.warning(f"Requested {direct_message_channels} DM conversations but only {len(other_users)} other users available")
        logger.info("Will create group DMs to reach the requested number of conversations")

    logger.info(f"Selected owner '{owner_user['username']}' and {len(other_users)} other users for DM generation")

    if not other_users:
        logger.warning("No other users found to create DMs with owner")
        return

    # Generate DM groups (1-on-1 or group DMs)
    dm_groups_with_dates = []

    # Create a pool of valid users that can communicate with the owner
    valid_users = []
    for member in other_users:
        can_communicate, earliest_date = _can_users_communicate(owner_user, member)
        if can_communicate and random.random() < 0.95:  # 95% chance of DM with owner (for testing)
            valid_users.append((member, earliest_date))

    if not valid_users:
        logger.warning(f"No valid users found for DMs with owner '{settings.MATTERMOST_OWNER_USERNAME}'")
        return

    # Generate exactly the requested number of DM conversations
    conversations_created = 0
    remaining_users = valid_users.copy()

    while conversations_created < direct_message_channels and remaining_users:
        # Decide if this should be a group DM or 1-on-1
        # If we have few conversations left or few users, prefer 1-on-1
        conversations_left = direct_message_channels - conversations_created
        users_left = len(remaining_users)

        # Create group DM if we have more users than conversations left and 30% chance
        should_create_group = users_left > conversations_left and random.random() < 0.3 and users_left >= 2

        if should_create_group:
            # Create group DM with 2-4 additional users (plus owner = 3-5 total)
            max_group_size = min(4, users_left, users_left - conversations_left + 1)
            group_size = random.randint(2, max_group_size)
            selected_members = random.sample(remaining_users, group_size)

            # Get all users in this group (owner + selected members)
            group_users = [owner_user] + [member for member, _ in selected_members]
            # Use the LATEST communication date among all members (when ALL can communicate)
            earliest_date = max(date for _, date in selected_members)

            dm_groups_with_dates.append((group_users, earliest_date))

            # Remove selected users from remaining pool
            for selected_member in selected_members:
                remaining_users.remove(selected_member)

            logger.info(f"Created group DM with {len(group_users)} users: {[u['username'] for u in group_users]}")
        else:
            random_index = random.randint(0, len(remaining_users) - 1)
            member, earliest_date = remaining_users.pop(random_index)
            group_users = [owner_user, member]
            dm_groups_with_dates.append((group_users, earliest_date))

            logger.info(f"Created 1-on-1 DM between: {owner_user['username']} and {member['username']}")

        conversations_created += 1

    # If we still need more conversations but ran out of users, create additional group DMs with remaining users
    if conversations_created < direct_message_channels and remaining_users:
        logger.info(f"Need {direct_message_channels - conversations_created} more conversations, creating group DMs with remaining users")
        while conversations_created < direct_message_channels and len(remaining_users) >= 2:
            # Create group DM with remaining users
            group_size = min(len(remaining_users), random.randint(2, 4))
            selected_members = random.sample(remaining_users, group_size)

            group_users = [owner_user] + [member for member, _ in selected_members]
            earliest_date = max(date for _, date in selected_members)

            dm_groups_with_dates.append((group_users, earliest_date))

            for selected_member in selected_members:
                remaining_users.remove(selected_member)

            logger.info(f"Created additional group DM with {len(group_users)} users: {[u['username'] for u in group_users]}")
            conversations_created += 1

    if not dm_groups_with_dates:
        logger.warning(f"No valid DM groups created for owner '{settings.MATTERMOST_OWNER_USERNAME}'")
        return

    # Use CLI parameters to control number of threads per DM, not messages per thread
    threads_per_dm_range = (min_threads_per_dm, max_threads_per_dm)
    # Fixed range for messages per thread (reasonable conversation length)
    messages_per_thread = random.randint(3, 8)

    # Process DM groups in batches for better performance
    all_dm_conversations = []
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATION_REQUESTS)

    async def _process_batch_with_semaphore(batch_groups_with_dates: list[tuple]) -> list[DirectMessages]:
        async with semaphore:
            return await _generate_dm_batch(batch_groups_with_dates, messages_per_thread, threads_per_dm_range, users_data)

    # Split groups into batches
    tasks = []
    for i in range(0, len(dm_groups_with_dates), settings.MAX_CONCURRENT_GENERATION_REQUESTS):
        batch = dm_groups_with_dates[i : i + settings.MAX_CONCURRENT_GENERATION_REQUESTS]
        tasks.append(_process_batch_with_semaphore(batch))

    # Execute all batches concurrently
    batch_results = await asyncio.gather(*tasks)

    # Flatten results
    for batch_result in batch_results:
        all_dm_conversations.extend(batch_result)

    if not all_dm_conversations:
        logger.warning("No DM conversations were generated")
        return

    # Save to JSON file
    logger.info(f"Saving {len(all_dm_conversations)} DM conversations to {DM_PATH}")

    # Prepare data for JSON serialization using shared utility
    dm_data_for_json = []
    for dm in all_dm_conversations:
        dm_dict = dm.model_dump()

        # Process threads using shared utility
        threads_data = dm_dict.get("threads", [])
        dm_dict["threads"] = prepare_threads_for_json([Thread(**thread_data) for thread_data in threads_data])

        dm_data_for_json.append(dm_dict)

    save_to_json(dm_data_for_json, DM_PATH)
    total_messages = sum(len(thread.messages) for dm in all_dm_conversations for thread in dm.threads)
    logger.succeed(f"Generated {len(all_dm_conversations)} direct message conversations with {total_messages} total messages")


async def insert_direct_messages():
    direct_messages: list[DirectMessages] = load_json(DM_PATH)
    users_data = load_json(USERS_PATH)

    logger.start(f"Inserting {len(direct_messages)} direct messages channels...")

    try:
        async with MattermostClient() as client:
            try:
                mattermost_users: list[dict] = await client.get_users()

                # Add the same password to all users (as done elsewhere in the codebase)
                for user in mattermost_users:
                    user["password"] = settings.MATTERMOST_PASSWORD

                # Create lookup by Mattermost user ID
                users_by_mattermost_id_lookup: dict[str, dict] = {user["id"]: user for user in mattermost_users}

                # Create lookup by username to get Mattermost IDs
                username_to_mattermost_id: dict[str, str] = {user["username"]: user["id"] for user in mattermost_users}

                # Create lookup by local ID to get username
                local_id_to_username: dict[int, str] = {user["id"]: user["username"] for user in users_data}

            except Exception as e:
                logger.fail(f"Failed to get users: {e}")
                return

        for dm in direct_messages:
            members: list[int] = dm.get("members", []) or []

            # Convert local integer IDs to Mattermost UUIDs
            member_ids: list[str] = []
            for local_id in members:
                username = local_id_to_username.get(local_id)
                if username:
                    mattermost_id = username_to_mattermost_id.get(username)
                    if mattermost_id:
                        member_ids.append(mattermost_id)
                    else:
                        logger.warning(f"No Mattermost ID found for username {username}")
                else:
                    logger.warning(f"No username found for local ID {local_id}")

            if not member_ids:
                continue

            if len(member_ids) < 2 or len(member_ids) > 7:
                logger.warning(f"Direct channel requires 2-7 users, got {len(member_ids)}: {member_ids}")
                continue

            # Pick a random member from this DM to create the channel (more realistic)
            random_member_id = random.choice(member_ids)
            random_member_user = users_by_mattermost_id_lookup.get(random_member_id)

            if not random_member_user:
                logger.warning(f"Could not find user data for member {random_member_id}, using default client")
                async with MattermostClient() as client:
                    private_channel = await client.create_direct_channel(member_ids)
            else:
                # Use the random member's credentials to create the channel
                async with MattermostClient(username=random_member_user["username"], password=random_member_user["password"]) as client:
                    private_channel = await client.create_direct_channel(member_ids)

            # Mark the channel as viewed to make it visible in UI for the admin user
            if private_channel and private_channel.get("id"):
                # Use the admin user ID to show the direct channel in UI
                admin_user_id = username_to_mattermost_id.get(settings.MATTERMOST_OWNER_USERNAME)
                if admin_user_id:
                    admin_user = users_by_mattermost_id_lookup.get(admin_user_id)
                    if admin_user:
                        # Create admin client for setting preferences
                        async with MattermostClient(username=admin_user["username"], password=admin_user["password"]) as admin_client:
                            if len(member_ids) == 2:
                                # 1-on-1 DM: Find the other user ID (not the admin) for the direct channel preference
                                other_user_id = None
                                for member_id in member_ids:
                                    if member_id != admin_user_id:
                                        other_user_id = member_id
                                        break

                                if other_user_id:
                                    await admin_client.show_direct_channel(admin_user_id, private_channel["id"], other_user_id)
                                else:
                                    # Fallback: let the method auto-detect the other user
                                    await admin_client.show_direct_channel(admin_user_id, private_channel["id"])
                            else:
                                # Group DM: Use group channel preferences
                                preferences = [
                                    {"user_id": admin_user_id, "category": "group_channel_show", "name": private_channel["id"], "value": "true"},
                                    {"user_id": admin_user_id, "category": "channel_open_time", "name": private_channel["id"], "value": str(int(time.time() * 1000))},
                                ]
                                await admin_client.set_user_preferences(admin_user_id, preferences)

            if private_channel:
                for thread in dm.get("threads", []) or []:
                    thread_messages = thread.get("messages", []) or []
                    has_root_message = thread.get("has_root_message", False)
                    root_post_id = None  # Will be set to first message ID if has_root_message is True

                    for msg_idx, msg in enumerate(thread_messages):
                        # msg["from_user"] is a local integer ID, need to convert to Mattermost ID
                        local_from_user_id = msg["from_user"]
                        from_username = local_id_to_username.get(local_from_user_id)

                        if not from_username:
                            logger.warning(f"No username found for local ID {local_from_user_id}, skipping message")
                            continue

                        from_mattermost_id = username_to_mattermost_id.get(from_username)
                        if not from_mattermost_id:
                            logger.warning(f"No Mattermost ID found for username {from_username}, skipping message")
                            continue

                        user: dict[str, str] = users_by_mattermost_id_lookup.get(from_mattermost_id)
                        if not user:
                            logger.warning(f"User with Mattermost ID {from_mattermost_id} not found, skipping message")
                            continue

                        # Use timestamp as create_at if available, otherwise use current time
                        create_at = msg.get("timestamp", int(datetime.datetime.now().timestamp() * 1000))

                        async with MattermostClient(username=user["username"], password=user["password"]) as upload_client:
                            # Handle file attachments if LLM specified filenames
                            file_ids = await handle_file_attachments(msg, private_channel["id"], upload_client)

                        # Create post data using shared utility (no user_id to respect custom timestamps)
                        post_data = create_base_post_data(
                            channel_id=private_channel["id"],
                            message_content=msg.get("content"),
                            timestamp=create_at,
                            root_id=root_post_id if (has_root_message and msg_idx > 0 and root_post_id) else None,
                            file_ids=file_ids if file_ids else None,
                        )

                        async with MattermostClient(username=user["username"], password=user["password"]) as client:
                            try:
                                # Create the message
                                main_post = await client.create_post(post_data=post_data)

                                # Update timestamp in database to ensure it's properly set
                                if main_post and main_post.get("id"):
                                    await update_post_timestamp(main_post["id"], create_at)

                                # Store the first message ID as root for subsequent threaded replies
                                if main_post and main_post.get("id") and msg_idx == 0:
                                    root_post_id = main_post["id"]

                                # Handle message features using shared modules
                                if main_post and main_post.get("id"):
                                    # Handle pinning
                                    await handle_message_pinning(msg, main_post["id"], client)

                                    # Handle reactions with proper user authentication
                                    await handle_message_reactions(msg, main_post["id"], member_ids, users_by_mattermost_id_lookup)

                                await asyncio.sleep(0.5)

                            except Exception as e:
                                logger.fail(f"Failed to create direct messages: {e}")

                    # Update threads table if this thread has replies and has_root_message is True
                    if has_root_message and root_post_id and len(thread_messages) > 1:
                        # Get the last message timestamp
                        last_message_timestamp = thread_messages[-1].get("timestamp") if thread_messages else None

                        await _update_dm_thread_metadata(
                            root_post_id=root_post_id,
                            last_reply_timestamp=last_message_timestamp,
                        )

        logger.succeed(f"Inserted {len(direct_messages)} direct messages")

    finally:
        # Clean up the timestamp processor and process remaining updates
        logger.info("Processing remaining timestamp updates...")
        # Timestamp processor cleanup no longer needed
        logger.succeed("Completed timestamp updates")
