"""Post feature handling for Mattermost messages (pinning, reactions)."""

import random
from typing import Any

from apps.mattermost.utils.constants import DM_REACTION_MAX_PARTICIPATION, DM_REACTION_MIN_PARTICIPATION
from apps.mattermost.utils.mattermost import MattermostClient
from common.logger import logger


async def handle_message_pinning(
    message: dict[str, Any],
    post_id: str,
    client: MattermostClient,
) -> bool:
    """
    Handle message pinning if requested.

    Args:
        message: Message data containing is_pinned flag
        post_id: ID of the post to pin
        client: Authenticated MattermostClient instance

    Returns:
        True if pinning was successful or not needed, False if failed
    """
    if not message.get("is_pinned", False):
        return True  # No pinning needed

    try:
        await client.pin_post(post_id)
        # logger.debug(f"Pinned message {post_id}")
        return True
    except Exception as e:
        logger.debug(f"Failed to pin message {post_id}: {e}")
        return False


async def handle_message_reactions(
    message: dict[str, Any],
    post_id: str,
    member_ids: list[str] | None = None,
    users_by_id: dict[str, dict] | None = None,
) -> bool:
    """
    Handle message reactions if requested.

    Args:
        message: Message data containing has_reactions flag
        post_id: ID of the post to add reactions to
        client: Authenticated MattermostClient instance (kept for backward compatibility)
        member_ids: List of member IDs who can react (for random selection)
        users_by_id: Dictionary mapping user IDs to user data (username only, password is shared)

    Returns:
        True if reaction handling was successful or not needed, False if failed
    """
    if not message.get("has_reactions", False):
        return True  # No reactions needed

    try:
        # Available emoji reactions
        reaction_emojis = ["thumbsup", "heart", "laughing", "tada", "fire", "eyes", "rocket", "clap"]

        if not member_ids or not users_by_id:
            logger.debug(f"No member_ids or users_by_id provided for reactions on post {post_id}")
            return True

        participant_count = len(member_ids)

        # Calculate total number of individual reactions (multiple users can use same emoji)
        min_total_reactions = max(1, int(participant_count * DM_REACTION_MIN_PARTICIPATION))
        max_total_reactions = max(2, int(participant_count * DM_REACTION_MAX_PARTICIPATION * 1.5))  # Increased for multiple same-type reactions
        total_reactions = random.randint(min_total_reactions, max_total_reactions)

        # Select 2-4 different emoji types to use (fewer unique emojis, more reactions per emoji)
        num_emoji_types = min(random.randint(2, 4), len(reaction_emojis))
        selected_emoji_types = random.sample(reaction_emojis, num_emoji_types)

        # Distribute total reactions across the selected emoji types
        reactions_to_add = []
        reactions_per_emoji = []

        # Create a weighted distribution (some emojis get more reactions than others)
        for i, _emoji in enumerate(selected_emoji_types):
            if i == len(selected_emoji_types) - 1:
                # Last emoji gets remaining reactions
                remaining = total_reactions - sum(reactions_per_emoji)
                reactions_per_emoji.append(max(1, remaining))
            else:
                # Random allocation with bias towards 1-3 reactions per emoji
                max_for_this = min(total_reactions - len(selected_emoji_types) + i + 1, participant_count)
                reactions_for_this = random.randint(1, max(1, max_for_this // 2))
                reactions_per_emoji.append(reactions_for_this)

        # Create individual reaction assignments
        for emoji, count in zip(selected_emoji_types, reactions_per_emoji, strict=True):
            # Select random users for this emoji (can pick same user multiple times, but Mattermost will dedupe)
            for _ in range(count):
                reactor_id = random.choice(member_ids)
                reactions_to_add.append((emoji, reactor_id))

        # Shuffle to mix different emoji types randomly
        random.shuffle(reactions_to_add)

        # Track which users have already reacted with which emojis to avoid duplicates
        user_emoji_reactions = set()

        # Add reactions
        from apps.mattermost.config.settings import settings
        from apps.mattermost.utils.mattermost import MattermostClient

        for emoji, reactor_id in reactions_to_add:
            # Skip if this user already reacted with this emoji
            user_emoji_key = (reactor_id, emoji)
            if user_emoji_key in user_emoji_reactions:
                continue

            reactor_user = users_by_id.get(reactor_id)
            if reactor_user and reactor_user.get("username"):
                try:
                    async with MattermostClient(username=reactor_user["username"], password=settings.MATTERMOST_PASSWORD) as reactor_client:
                        await reactor_client.create_reaction(post_id, reactor_id, emoji)
                        user_emoji_reactions.add(user_emoji_key)
                        # logger.debug(f"Added {emoji} reaction to message {post_id} by user {reactor_user['username']}")
                except Exception as e:
                    logger.debug(f"Failed to add {emoji} reaction by user {reactor_user['username']}: {e}")
            else:
                logger.debug(f"No user data found for reactor ID {reactor_id}, skipping reaction")

        return True
    except Exception as e:
        logger.debug(f"Failed to add reactions to message {post_id}: {e}")
        return False
