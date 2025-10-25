import random

from apps.mattermost.utils.constants import (
    CHANNEL_REACTION_HIGH_MAX_PARTICIPATION,
    CHANNEL_REACTION_HIGH_MIN_PARTICIPATION,
    CHANNEL_REACTION_LOW_MAX_PARTICIPATION,
    CHANNEL_REACTION_LOW_MIN_PARTICIPATION,
)


default_emojis = ["+1", "heart", "smile", "thumbsup", "fire", "tada", "eyes", "white_check_mark", "thinking"]  # Example default emojis,

Reactions = dict[str, dict[str, list[str]]]


def generate_random_reactions(usernames: list[str], emojis: list[str] = default_emojis, has_reactions: bool = False) -> Reactions:
    result: Reactions = {}

    # Add chance for no reactions
    if not has_reactions and random.random() < 0.7:
        return result

    # Calculate proportional reactions based on participant count
    participant_count = len(usernames)
    if has_reactions:
        # Higher participation for messages marked as needing reactions
        min_reactions = max(1, int(participant_count * CHANNEL_REACTION_HIGH_MIN_PARTICIPATION))
        max_reactions = max(1, int(participant_count * CHANNEL_REACTION_HIGH_MAX_PARTICIPATION))
        total_reactions = random.randint(min_reactions, max_reactions)
    else:
        # Lower participation for regular messages
        min_reactions = max(1, int(participant_count * CHANNEL_REACTION_LOW_MIN_PARTICIPATION))
        max_reactions = max(1, int(participant_count * CHANNEL_REACTION_LOW_MAX_PARTICIPATION))
        total_reactions = random.randint(min_reactions, max_reactions)

    # Ensure we don't exceed available users
    total_reactions = min(total_reactions, len(usernames))

    if total_reactions == 0:
        return result

    # Determine how many different emoji types to use (fewer types, more reactions per type)
    max_emoji_types = min(total_reactions, len(emojis), 4)  # At most 4 different emoji types
    num_emoji_types = random.randint(1, max_emoji_types)

    # Randomly select emoji types
    selected_emojis = random.sample(emojis, num_emoji_types)

    # Distribute total reactions across the selected emojis
    reactions_per_emoji = []
    remaining_reactions = total_reactions

    for i in range(num_emoji_types):
        if i == num_emoji_types - 1:  # Last emoji gets all remaining reactions
            reactions_per_emoji.append(remaining_reactions)
        else:
            # Give this emoji 1 to (remaining_reactions - remaining_emojis + 1) reactions
            max_for_this = max(1, remaining_reactions - (num_emoji_types - i - 1))
            reactions_for_this = random.randint(1, max_for_this)
            reactions_per_emoji.append(reactions_for_this)
            remaining_reactions -= reactions_for_this

    # Assign users to emojis
    available_users = usernames.copy()
    random.shuffle(available_users)
    user_index = 0

    for emoji, num_reactions in zip(selected_emojis, reactions_per_emoji, strict=False):
        selected_users = []
        for _ in range(num_reactions):
            if user_index < len(available_users):
                selected_users.append(available_users[user_index])
                user_index += 1
            else:
                # If we run out of unique users, start reusing them
                selected_users.append(random.choice(usernames))

        result[emoji] = selected_users

    return result
