import asyncio
import datetime
import random
from pathlib import Path

from pydantic import BaseModel, Field

from apps.mattermost.config.settings import settings
from apps.mattermost.core.messages import (
    convert_llm_to_complete_messages,
    create_attachment_instructions,
    create_business_theme_context,
    create_current_date_context,
    create_markdown_guidelines,
    create_thread_context_prompt,
    generate_thread_message_timestamps,
    generate_thread_with_llm,
    set_probabilistic_thread_attributes,
)
from apps.mattermost.models.message import (
    ChannelMessageResponse,
    ChannelThreads,
    Message,
    Thread,
)
from apps.mattermost.utils.ai import instructor_client
from apps.mattermost.utils.constants import CHANNEL_MESSAGE_REACTION_PROBABILITY, THREAD_ATTACHMENT_PROBABILITY
from apps.mattermost.utils.openai import get_system_prompt
from common.load_json import load_json
from common.logger import logger
from common.save_to_json import save_to_json


TEAMS_PATH = settings.DATA_PATH.joinpath("teams.json")

BATCH_SIZE = 35


def _set_probabilistic_message_attributes(messages: list[Message]) -> list[Message]:
    """Set is_pinned and has_reactions probabilistically for messages."""
    for message in messages:
        # Set is_pinned with 5% probability
        message.is_pinned = random.random() < 0.05

        # Set has_reactions with configurable probability
        message.has_reactions = random.random() < (CHANNEL_MESSAGE_REACTION_PROBABILITY / 100)

    return messages


def _create_message_context_prompt(messages: list[Message]) -> str:
    """Create context prompt with probabilistic message attributes."""
    context_lines = []
    for i, message in enumerate(messages, 1):
        pin_status = "PINNED" if message.is_pinned else "not pinned"
        reaction_status = "MUST have reactions" if message.has_reactions else "optional reactions"
        context_lines.append(f"Message {i}: {pin_status}, {reaction_status}")

    return "\n".join(context_lines)


class ThreadCountResponse(BaseModel):
    """Response model for determining optimal thread count for a channel."""

    thread_count: int = Field(description="The optimal number of threads this channel should have based on its characteristics", ge=1)


async def _generate_channel_messages_per_channel_batch(channel_name: str, members: list[tuple], count: int) -> list[Message]:
    """Generates a single batch of channel messages and returns the list."""

    # First, create empty message objects with probabilistic attributes
    messages_with_attributes = []
    for _ in range(count):
        message = Message(from_user=1, content="placeholder")  # Temporary values
        messages_with_attributes.append(message)

    # Apply probabilistic attributes
    messages_with_attributes = _set_probabilistic_message_attributes(messages_with_attributes)

    # Create context about the probabilistic attributes for the LLM
    message_context = _create_message_context_prompt(messages_with_attributes)

    # Get current time context for the LLM
    current_time = datetime.datetime.now()
    current_date_str = current_time.strftime("%Y-%m-%d")

    user_prompt = f"""
        Generate {count} messages on Mattermost channel "${channel_name}". 
        This channel is about "${channel_name}" and the business theme is {settings.DATA_THEME_SUBJECT}.

        **Current Time Context:**
        - Today's Date: {current_date_str}
        - Use this as reference for any time-sensitive content (e.g., "this week", "today", "tomorrow", etc.)

        Available users & positions with format [(username, position), etc.] for this channel: {members}

        **Message Attributes (already determined probabilistically):**
        {message_context}

        Requirements:
        - All the topics should be relevant to the channel name and business theme (software products, IT systems, integrations, or service delivery, etc.).
        - Use the current time context to create realistic, time-sensitive content (meetings "today", deadlines "this week", etc.)
        - Reference appropriate timeframes based on today's date for realistic workplace scenarios
        - Only use usernames from the list above.
        - The messages should be professional and detailed, using markdown naturally when it improves clarity.
        - 30% of messages are 1 to 2 sentence long (quick replies, confirmations, brief updates).
        - 70% of messages are multi-paragraph long (2-5 paragraphs), with detailed explanations, comprehensive updates, thorough analysis, or extensive documentation.
        - Messages should be a mix of questions, announcements, reminders, professional discussions, detailed updates, asking for help, project reports, technical explanations, etc.
        - Multi-paragraph messages should use markdown naturally when it improves clarity (lists for steps, code snippets for technical terms, etc.).
        - Longer messages should contain detailed information, structured content, and professional communication typical of team channels.
        - The number of replies should be very varied, depending on the length of messages so that it looks like a real conversation.
        - For multi-paragraph messages, make sure to have 8-15 replies to reflect the detailed discussion they would generate.
        - For messages with 1-2 sentences, make sure to have 1-4 replies.
        - The number of replies should not be duplicated too much.
        - For 2 consecutive messages, make sure that the first message has replies and the second one has different no of replies.
        - More detailed and longer messages should have more replies.
        - And add gap between messages that have replies, so that it looks like a real conversation.
        - Use markdown selectively when it adds value - don't force formatting where plain text flows better.
        - Make sure that threads and messages make sense and are appropriate for team channel discussions.
        - At least 1 user has multiples messages in the thread.
        - Each member should have at least 1 message and 1 reply.
        - Each message should have varied reply counts based on content complexity.
        - The message should be relevant to the user's position and demonstrate professional expertise.
        - When mentioning an user in the message, use @username, don't add any special characters.
        - Do not need always mention users in the message, only mentions for questions in replies.
        - If sender or replier is {settings.MATTERMOST_OWNER_USERNAME}, the message should be relevant to mattermost platform support like adding new members to team or channel, 
        reset password, update permission, etc.
        
        {create_markdown_guidelines(is_team_channel=True)}
        
        **Important:** Use the message attribute context above to inform your content generation. 
        Messages marked as PINNED should be important announcements or updates. 
        Messages that MUST have reactions should be engaging content that would naturally attract reactions.
    """

    response = await instructor_client.chat.completions.create(
        model=settings.DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        response_model=ChannelMessageResponse,
        temperature=0.7,
        max_tokens=settings.MAX_OUTPUT_TOKENS,
    )

    if not response:
        logger.warning("No channel messages generated. Please generate again.")
        return []

    # Apply the probabilistic attributes to the generated messages
    generated_messages = response.messages
    for i, message in enumerate(generated_messages):
        if i < len(messages_with_attributes):
            message.is_pinned = messages_with_attributes[i].is_pinned
            message.has_reactions = messages_with_attributes[i].has_reactions

    return generated_messages


async def _generate_thread_messages_unified(
    channel_name: str, channel_description: str, available_users: list[tuple], thread_start_timestamp: int, thread_end_timestamp: int, thread_number: int
) -> Thread:
    """Generate messages for a single thread with timestamp constraints and available users.

    Args:
        available_users: List of tuples (user_id, username, position) for users available at thread time
    """

    # Convert timestamps to readable format for the prompt
    start_dt = datetime.datetime.fromtimestamp(thread_start_timestamp / 1000)
    end_dt = datetime.datetime.fromtimestamp(thread_end_timestamp / 1000)

    # Calculate realistic message count for this thread (3-15 messages per thread)
    base_message_count = random.randint(3, 8)
    # More users = potential for more messages, but cap it
    user_factor = min(len(available_users) / 5, 2.0)
    thread_message_count = min(int(base_message_count * user_factor), 15)

    # Create thread template with messages
    thread_messages = []
    for _ in range(thread_message_count):
        message = Message(from_user=1, content="placeholder")  # Temporary values
        thread_messages.append(message)

    # Create thread with messages
    thread_template = Thread(messages=thread_messages)

    # Apply probabilistic attributes to the thread
    threads_with_attributes = set_probabilistic_thread_attributes([thread_template], context_type="channel", attachment_probability=THREAD_ATTACHMENT_PROBABILITY)
    thread_with_attributes = threads_with_attributes[0]

    # Create context about the probabilistic attributes for the LLM
    thread_context = create_thread_context_prompt([thread_with_attributes])

    # Determine attachment instructions based on thread flag
    attachment_instruction = create_attachment_instructions(getattr(thread_with_attributes, "should_have_attachments", False))

    # Get current time context for the LLM using shared utility
    current_date_context = create_current_date_context()

    user_prompt = f"""
        Generate {thread_message_count} messages for Thread #{thread_number} in Mattermost channel "{channel_name}".
        Channel Description: "{channel_description}"
        {create_business_theme_context()}

        {current_date_context}

        **Thread Timeline:**
        - Thread Start: {start_dt.strftime("%Y-%m-%d %H:%M:%S")}
        - Thread End: {end_dt.strftime("%Y-%m-%d %H:%M:%S")}
        - Duration: {(thread_end_timestamp - thread_start_timestamp) // (60 * 60 * 1000)} hours

        **Available Participants (choose from these for each message's from_user):**
        {chr(10).join([f"- User ID {user_id}: {username} ({position})" for user_id, username, position in available_users])}

        **Thread and Message Attributes (already determined probabilistically):**
        {thread_context}

        **Thread Requirements:**
        - For each message, choose the appropriate from_user ID from the participants list above
        - Generate messages that are appropriate for different user positions/roles
        - Consider how different roles would interact in this conversation
        - Consider how different roles would interact (e.g., managers asking for updates, developers discussing technical details)
        - Create a focused conversation thread about a specific topic relevant to the channel
        - First message should be a clear thread starter (question, announcement, or discussion topic)
        - Subsequent messages should be replies that build on the conversation
        - Messages should feel natural and reference time context appropriately (use "today" as reference point)
        - When the thread occurred in the past, create content that would have been relevant at that time
        - Each user should contribute meaningfully to the discussion
        - Thread should have a natural conversation flow and resolution
        - When mentioning a user in the message, use @username format (e.g., @robert.jenkins) - don't add any special characters
        - Use mentions naturally when asking questions or directing comments to specific participants in replies
        - DO NOT include timestamps in the message content - these will be added programmatically

        **Message Distribution:**
        - 1 thread starter message (the initial post)
        - {thread_message_count - 1} reply messages from different users
        - Ensure the thread starter gets some replies
        - Mix of short responses (1-2 sentences) and longer explanations (2-5 paragraphs for detailed discussions)
        
        {create_markdown_guidelines(is_team_channel=True)}
        {attachment_instruction}

        **Topic Ideas for "{channel_name}":**
        - Technical discussions, project updates, questions for help
        - Collaborative problem-solving, sharing resources/links
        - Status updates, meeting coordination, decision making
        - Knowledge sharing, best practices, lessons learned

        **Important:** Use the message attribute context above to inform your content generation. 
        Messages marked as PINNED should be important announcements or updates. 
        Messages that MUST have reactions should be engaging content that would naturally attract reactions.

        Create a realistic conversation thread that feels authentic for this business context.
    """

    try:
        response = await generate_thread_with_llm(user_prompt, context_type=f"channel thread #{thread_number} in {channel_name}")

        if not response:
            return None

        # Convert LLM response to complete Thread using shared utility
        complete_messages = convert_llm_to_complete_messages(response, thread_with_attributes)

        # Generate realistic message timestamps using shared utility
        timestamps = generate_thread_message_timestamps(thread_start_timestamp, thread_end_timestamp, len(complete_messages))

        # Apply timestamps to messages
        for i, message in enumerate(complete_messages):
            if i < len(timestamps):
                message.timestamp = timestamps[i]

        messages_with_timestamps = complete_messages

        # Create the final Thread object with all attributes
        final_thread = Thread(
            messages=messages_with_timestamps,
            has_root_message=thread_with_attributes.has_root_message,
            should_have_attachments=getattr(thread_with_attributes, "should_have_attachments", None),
        )

        thread_duration_hours = (thread_end_timestamp - thread_start_timestamp) // (60 * 60 * 1000)
        logger.debug(f"Generated thread #{thread_number} in {channel_name} with {len(messages_with_timestamps)} messages spanning {thread_duration_hours} hours")
        return final_thread

    except Exception as e:
        logger.error(f"Failed to generate thread messages for {channel_name} thread #{thread_number}: {e}")
        return None


async def _process_single_channel_threads(channel_data: dict) -> None:
    """Process a single channel to generate thread-based messages with proper user filtering."""
    team_name = channel_data["team_name"]
    channel_name = channel_data["channel_name"]
    channel_description = channel_data["channel_description"]
    members_with_join_dates = channel_data["members"]
    thread_timestamps = channel_data["thread_timestamps"]

    # Check if we have any viable thread timestamps
    if not thread_timestamps:
        logger.info(f"⚠ No viable thread timestamps for channel: {team_name}/{channel_name} (insufficient users throughout channel history)")
        return

    logger.info(f"Generating {len(thread_timestamps)} threads for channel: {team_name}/{channel_name}")

    # Special handling for town-square channel - COMMENTED OUT FOR NOW
    # if channel_name == "town-square":
    #     # Convert members to expected format for town-square function
    #     users = [{"user_id": member["user_id"], "username": member["username"], "position": member["position"]} for member in members_with_join_dates]
    #     await _generate_town_square_messages(len(thread_timestamps), users, team_name)
    #     return

    all_threads = []

    # Generate threads for each timestamp
    for thread_index, thread_timestamp in enumerate(thread_timestamps):
        # Filter users who had joined the channel by this thread's timestamp
        available_users = []
        for member in members_with_join_dates:
            if member["joined_at"] <= thread_timestamp:
                available_users.append((member["user_id"], member["username"], member["position"]))

        if len(available_users) < 2:
            logger.debug(f"Skipping thread {thread_index + 1} in {team_name}/{channel_name}: insufficient users ({len(available_users)}) at timestamp {thread_timestamp}")
            continue

        # Calculate thread end time (for realistic conversation duration)
        # Threads typically last a few hours to a few days
        thread_duration_hours = random.randint(2, 48)  # 2 hours to 2 days
        thread_end_timestamp = thread_timestamp + (thread_duration_hours * 60 * 60 * 1000)

        # Generate thread for this timestamp
        try:
            thread = await _generate_thread_messages_unified(
                channel_name=channel_name,
                channel_description=channel_description,
                available_users=available_users,
                thread_start_timestamp=thread_timestamp,
                thread_end_timestamp=thread_end_timestamp,
                thread_number=thread_index + 1,
            )
            if thread:
                all_threads.append(thread)

        except Exception as e:
            logger.error(f"Failed to generate thread {thread_index + 1} for {team_name}/{channel_name}: {e}")
            continue

    if not all_threads:
        logger.warning(f"No threads were generated for {team_name}/{channel_name}")
        return

    # Save threads structure to file
    filename = f"{team_name}.{channel_name}.json"
    path = settings.DATA_PATH.joinpath(f"channel-messages/{filename}")

    # Create ChannelThreads object and serialize to JSON
    channel_threads = ChannelThreads(threads=all_threads)
    threads_data = channel_threads.model_dump()

    save_to_json(threads_data, path)

    total_messages = sum(len(thread.messages) for thread in all_threads)
    logger.info(f"Generated {total_messages} messages across {len(all_threads)} threads for channel: {team_name}/{channel_name}")


async def _process_single_channel(team_name: str, channel_name: str, members: list[tuple], count: int) -> None:
    """Process a single channel to generate messages."""
    logger.info(f"Generating messages for channel: {team_name}/{channel_name}")

    # Special handling for town-square channel - COMMENTED OUT FOR NOW
    # if channel_name == "town-square":
    #     # Convert members list to users list format expected by town-square function
    #     users = [{"user_id": user_id, "username": username, "position": position} for user_id, username, position in members]
    #     await _generate_town_square_messages(count, users, team_name)
    #     return

    # Regular channel message generation
    tasks = []
    remaining_count = count

    while remaining_count > 0:
        current_batch_size = min(BATCH_SIZE, remaining_count)
        tasks.append(_generate_channel_messages_per_channel_batch(channel_name, members, current_batch_size))
        remaining_count -= current_batch_size

    # Run all tasks concurrently and wait for them to complete
    responses: list[Message] = await asyncio.gather(*tasks)

    channel_messages = []
    for res in responses:
        channel_messages.extend(res)

    if not channel_messages:
        logger.warning(f"No channel messages were generated for {team_name}/{channel_name}. Please try again.")
        return

    # Include team name in filename to avoid overwrites using dot notation
    filename = f"{team_name}.{channel_name}.json"
    path = settings.DATA_PATH.joinpath(f"channel-messages/{filename}")

    # Prepare messages for JSON with timestamps
    messages_for_json = []
    for message in channel_messages:
        message_dict = message.model_dump()
        # Ensure timestamp is included
        if hasattr(message, "timestamp"):
            message_dict["timestamp"] = message.timestamp
        elif "timestamp" not in message_dict:
            message_dict["timestamp"] = int(datetime.datetime.now().timestamp() * 1000)
        messages_for_json.append(message_dict)

    save_to_json(messages_for_json, path)
    logger.info(f"Generated {len(channel_messages)} messages for channel: {team_name}/{channel_name}")


async def generate_channel_messages(min_threads_per_channel: int, max_threads_per_channel: int):
    """
    Generates channel messages using asyncio.gather for concurrent processing.
    Uses LLM to determine optimal thread count per channel based on characteristics.
    """
    # Delete all contents in the channel-messages folder before generating new messages
    channel_messages_path = settings.DATA_PATH.joinpath("channel-messages")
    if channel_messages_path.exists() and channel_messages_path.is_dir():
        for file in channel_messages_path.iterdir():
            if file.is_file():
                file.unlink()
    Path.mkdir(channel_messages_path, exist_ok=True)

    # Load teams and users data
    teams_data = load_json(TEAMS_PATH)
    users_data = load_json(settings.DATA_PATH.joinpath("users.json"))

    channels_to_process = []

    # Process each team and their channels
    for team in teams_data:
        team_name = team["name"]
        team_channels = team.get("channels", [])

        for channel in team_channels:
            channel_name = channel["name"]
            channel_description = channel.get("description", "")
            channel_created_at = channel.get("created_at", int(datetime.datetime.now().timestamp() * 1000))

            # Find users who are members of this channel
            channel_members = []
            for user in users_data:
                user_team_channels = user.get("team_channels", {}).get(team_name, {})
                if channel_name in user_team_channels:
                    channel_members.append((user["username"], user.get("position", "Unknown")))

            if not channel_members:
                logger.warning(f"No members found for channel {team_name}/{channel_name}, skipping")
                continue

            # Get users with their join dates for this channel
            channel_members_with_join_dates = []
            for user in users_data:
                user_team_channels = user.get("team_channels", {}).get(team_name, {})
                if channel_name in user_team_channels:
                    channel_info = user_team_channels[channel_name]
                    joined_at = channel_info.get("joined_at", channel_created_at)
                    channel_members_with_join_dates.append({"user_id": user["id"], "username": user["username"], "position": user.get("position", "Unknown"), "joined_at": joined_at})

            # Store channel info for concurrent processing
            channels_to_process.append(
                {
                    "team_name": team_name,
                    "channel_name": channel_name,
                    "channel_description": channel_description,
                    "channel_created_at": channel_created_at,
                    "members": channel_members_with_join_dates,
                    "min_threads_per_channel": min_threads_per_channel,
                    "max_threads_per_channel": max_threads_per_channel,
                }
            )

    logger.info(f"Total channels to process: {len(channels_to_process)}")

    # Step 1: Concurrently determine thread counts for all channels
    thread_count_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATION_REQUESTS)

    async def _determine_channel_threads(channel_data: dict) -> dict:
        """Determine thread count and timestamps for a single channel."""
        async with thread_count_semaphore:
            try:
                # Use LLM to determine optimal thread count
                min_val = channel_data["min_threads_per_channel"]
                max_val = channel_data["max_threads_per_channel"]

                thread_count = await determine_threads_per_channel(
                    min_threads_per_channel=min_val,
                    max_threads_per_channel=max_val,
                    channel_name=channel_data["channel_name"],
                    channel_description=channel_data["channel_description"],
                    channel_created_at=channel_data["channel_created_at"],
                    number_of_users=len(channel_data["members"]),
                )

                logger.info(f"Channel '{channel_data['channel_name']}' assigned {thread_count} threads (range: {min_val}-{max_val})")
            except Exception as e:
                logger.error(f"Failed to determine thread count for {channel_data['team_name']}/{channel_data['channel_name']}: {e}")
                thread_count = channel_data["min_threads_per_channel"]

            try:
                # Extract member join dates for better thread timing
                member_join_dates = [member["joined_at"] for member in channel_data["members"]]

                # Generate thread timestamps
                thread_timestamps = await generate_thread_timestamp_list(
                    channel_created_at=channel_data["channel_created_at"], thread_count=thread_count, members_join_dates=member_join_dates
                )
            except Exception as e:
                logger.error(f"Failed to generate thread timestamps for {channel_data['team_name']}/{channel_data['channel_name']}: {e}")
                thread_timestamps = []

            # Return updated channel data
            channel_data["thread_count"] = thread_count
            channel_data["thread_timestamps"] = thread_timestamps
            return channel_data

    logger.info(f"Determining thread counts for {len(channels_to_process)} channels concurrently (max {settings.MAX_CONCURRENT_GENERATION_REQUESTS} concurrent)")

    # Process all channels concurrently for thread count determination
    channels_with_threads = await asyncio.gather(*[_determine_channel_threads(channel_data) for channel_data in channels_to_process])

    logger.info(f"Thread count determination completed for {len(channels_with_threads)} channels")

    # Step 2: Generate messages for all channels with their determined thread counts
    message_generation_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_GENERATION_REQUESTS)

    async def _process_with_semaphore(channel_data: dict) -> None:
        async with message_generation_semaphore:
            await _process_single_channel_threads(channel_data)

    # Create tasks for all channels with their determined thread counts
    tasks = [_process_with_semaphore(channel_data) for channel_data in channels_with_threads]

    logger.info(f"Generating messages for {len(channels_with_threads)} channels concurrently (max {settings.MAX_CONCURRENT_GENERATION_REQUESTS} concurrent)")

    # Process all channels concurrently for message generation
    await asyncio.gather(*tasks)

    logger.succeed(f"Completed generating messages for all {len(channels_with_threads)} channels")


async def determine_threads_per_channel(
    min_threads_per_channel: int, max_threads_per_channel: int, channel_name: str, channel_description: str, channel_created_at: int, number_of_users: int
) -> int:
    today = int(datetime.datetime.now().timestamp() * 1000)

    # Calculate channel age in days
    channel_age_ms = today - channel_created_at
    channel_age_days = channel_age_ms // (24 * 60 * 60 * 1000)

    # Note: This function now uses heuristic-based calculation with randomization
    # instead of LLM-based determination for more reliable and consistent results

    # Always use heuristic-based calculation with randomization for more reliable variation
    # Don't rely solely on LLM which can be inconsistent or fail

    # Base threads per week based on channel type and user count
    base_weekly_threads = 0.2  # Conservative baseline

    # Adjust based on channel name and description patterns
    channel_text = f"{channel_name.lower()} {channel_description.lower()}"

    if any(keyword in channel_text for keyword in ["general", "off-topic", "random", "town-square", "casual", "chat", "discussion"]):
        base_weekly_threads = 1.5  # Higher activity channels
    elif any(keyword in channel_text for keyword in ["announcement", "important", "leadership", "read-only", "info", "updates"]):
        base_weekly_threads = 0.1  # Low activity channels
    elif any(keyword in channel_text for keyword in ["dev", "backend", "frontend", "engineering", "tech", "code", "development", "programming"]):
        base_weekly_threads = 0.8  # Moderate activity tech channels
    elif any(keyword in channel_text for keyword in ["marketing", "sales", "support", "client", "customer", "business"]):
        base_weekly_threads = 0.6  # Business team channels
    elif any(keyword in channel_text for keyword in ["project", "planning", "coordination", "management", "strategy"]):
        base_weekly_threads = 0.7  # Project management channels

    # Adjust for number of users (more users = more potential thread starters)
    user_factor = min(1.0 + (number_of_users - 10) * 0.03, 2.0)

    # Calculate total threads based on channel age
    channel_age_weeks = channel_age_days / 7
    base_estimate = int(channel_age_weeks * base_weekly_threads * user_factor)

    # Add significant randomization to ensure variety
    range_size = max_threads_per_channel - min_threads_per_channel

    # Use a more balanced approach: 50% heuristic + 50% random within range
    heuristic_weight = 0.4
    random_weight = 0.6

    # Scale base estimate to fit within range
    if base_estimate > 0:
        # Normalize base estimate to a 0-1 scale within the range
        normalized_base = min(base_estimate / (max_threads_per_channel * 0.7), 1.0)
        heuristic_value = min_threads_per_channel + (normalized_base * range_size)
    else:
        heuristic_value = min_threads_per_channel

    # Pure random value within range
    random_value = random.uniform(min_threads_per_channel, max_threads_per_channel)

    # Combine weighted heuristic and random
    thread_count = int(heuristic_weight * heuristic_value + random_weight * random_value)

    # Ensure within bounds
    thread_count = max(min_threads_per_channel, min(thread_count, max_threads_per_channel))

    # Add final variation to ensure no two channels are identical
    final_variation = random.randint(-1, 1)
    thread_count = max(min_threads_per_channel, min(thread_count + final_variation, max_threads_per_channel))

    # Special case: Double threads for town-square and off-topic channels (high activity)
    if channel_name.lower() in ["town-square", "off-topic"]:
        thread_count = min(thread_count * 2, max_threads_per_channel)
        logger.debug(f"Doubled thread count for high-activity channel '{channel_name}': {thread_count}")

    logger.debug(f"Channel '{channel_name}' ({channel_age_days}d old, {number_of_users} users): {thread_count} threads (heuristic: {heuristic_value:.1f}, random: {random_value:.1f})")

    return thread_count


async def generate_thread_timestamp_list(channel_created_at: int, thread_count: int, members_join_dates: list[int] | None = None) -> list[int]:
    """
    Generate realistic but sparse timestamps for thread creation.

    Args:
        channel_created_at: When the channel was created (timestamp in ms)
        thread_count: Number of threads to generate timestamps for
        members_join_dates: List of member join timestamps to ensure sufficient users

    Returns:
        List of timestamps in milliseconds, sorted chronologically
    """
    if thread_count <= 0:
        return []

    current_time = int(datetime.datetime.now().timestamp() * 1000)

    # Ensure we don't generate threads in the last 30 days (consistent with other timestamp logic)
    thirty_days_ago = current_time - (30 * 24 * 60 * 60 * 1000)

    # Consider member join dates to ensure threads have sufficient participants
    earliest_viable_thread_time = channel_created_at
    if members_join_dates and len(members_join_dates) >= 2:
        # Sort join dates and find when we have sufficient members for meaningful threads
        sorted_join_dates = sorted([date for date in members_join_dates if date >= channel_created_at])

        if len(sorted_join_dates) >= 4:
            # Wait for 4th member, then start threads relatively quickly
            fourth_member_time = sorted_join_dates[3]
            # Add short delay (1-3 days) after 4th member joins
            additional_delay = random.randint(1, 3) * 24 * 60 * 60 * 1000  # 1-3 days
            earliest_viable_thread_time = fourth_member_time + additional_delay

        elif len(sorted_join_dates) >= 3:
            # Wait for 3rd member, then add moderate delay
            third_member_time = sorted_join_dates[2]
            # Add 3-7 days delay after 3rd member joins
            additional_delay = random.randint(3, 7) * 24 * 60 * 60 * 1000  # 3-7 days
            earliest_viable_thread_time = third_member_time + additional_delay

        else:
            # If we only have 2 members, wait a bit longer for natural growth
            second_member_time = sorted_join_dates[1] if len(sorted_join_dates) >= 2 else sorted_join_dates[0]
            # Add 1-2 weeks delay - let channel establish itself
            additional_delay = random.randint(7, 14) * 24 * 60 * 60 * 1000  # 1-2 weeks
            earliest_viable_thread_time = second_member_time + additional_delay

    # Available time span for thread creation
    available_time_span = thirty_days_ago - earliest_viable_thread_time

    if available_time_span <= 0:
        # Channel is too new, create threads around channel creation time
        logger.warning("Channel created recently, generating threads near creation time")
        timestamps = []
        for _ in range(thread_count):
            # Spread threads over first few days after earliest viable time
            offset = random.randint(0, 7 * 24 * 60 * 60 * 1000)  # Within first week
            timestamp = earliest_viable_thread_time + offset
            timestamps.append(timestamp)
        return sorted(timestamps)

    timestamps = []

    # Create sparse, realistic thread distribution - but only for timestamps with sufficient users
    viable_timestamps = []

    for _ in range(thread_count * 3):  # Generate more candidates, filter for viable ones
        # Use exponential distribution to bias towards earlier dates (more activity when channel was newer)
        # but still spread threads across the entire timespan

        # Generate a random factor with exponential bias (more threads early, fewer later)
        random_factor = random.random() ** 1.5  # Bias towards 0 (earlier times)

        # Calculate base timestamp within available span
        time_offset = int(available_time_span * random_factor)
        base_timestamp = earliest_viable_thread_time + time_offset

        # Check how many users would be available at this timestamp
        users_at_timestamp = sum(1 for join_date in members_join_dates if join_date <= base_timestamp) if members_join_dates else 0

        # Skip this timestamp if there aren't enough users (minimum 2)
        if users_at_timestamp < 2:
            continue

        # Add realistic randomness to avoid threads appearing at exact mathematical intervals
        # Threads can be spread throughout days, but avoid clustering
        daily_variance = random.randint(-12 * 60 * 60 * 1000, 12 * 60 * 60 * 1000)  # ±12 hours

        # Ensure business hours bias (9 AM - 6 PM in various timezones)
        # This makes threads appear during typical work hours
        timestamp_dt = datetime.datetime.fromtimestamp(base_timestamp / 1000)

        # Adjust to business hours (bias towards 9 AM - 6 PM)
        if timestamp_dt.hour < 9 or timestamp_dt.hour > 18:
            # Move to business hours
            business_hour = random.randint(9, 18)
            business_minute = random.randint(0, 59)
            timestamp_dt = timestamp_dt.replace(hour=business_hour, minute=business_minute)
            base_timestamp = int(timestamp_dt.timestamp() * 1000)

        final_timestamp = base_timestamp + daily_variance

        # Ensure timestamp is within bounds
        final_timestamp = max(earliest_viable_thread_time + 1000, final_timestamp)
        final_timestamp = min(thirty_days_ago, final_timestamp)

        # Final check: ensure users are still available after all adjustments
        users_at_final_timestamp = sum(1 for join_date in members_join_dates if join_date <= final_timestamp) if members_join_dates else 0
        if users_at_final_timestamp < 3:
            continue

        viable_timestamps.append(final_timestamp)

        # Stop when we have enough viable timestamps
        if len(viable_timestamps) >= thread_count:
            break

    timestamps = viable_timestamps

    # Sort timestamps chronologically
    timestamps.sort()

    # Ensure minimum spacing between threads (prevent clustering)
    min_spacing = 2 * 60 * 60 * 1000  # Minimum 2 hours between threads
    adjusted_timestamps = []

    for i, timestamp in enumerate(timestamps):
        if i == 0:
            adjusted_timestamps.append(timestamp)
        else:
            # Ensure minimum spacing from previous thread
            min_allowed_time = adjusted_timestamps[-1] + min_spacing
            if timestamp < min_allowed_time:
                # Adjust timestamp to maintain spacing, but don't exceed our boundaries
                adjusted_timestamp = min(min_allowed_time, thirty_days_ago)
                adjusted_timestamps.append(adjusted_timestamp)
            else:
                adjusted_timestamps.append(timestamp)

    # Final validation - remove any timestamps that exceed thirty_days_ago due to spacing adjustments
    valid_timestamps = [ts for ts in adjusted_timestamps if ts <= thirty_days_ago]

    return valid_timestamps
