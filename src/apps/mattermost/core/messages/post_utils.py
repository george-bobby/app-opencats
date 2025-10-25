"""Utilities for creating Mattermost posts."""

import datetime
from typing import Any


def create_base_post_data(
    channel_id: str,
    message_content: str,
    user_id: str | None = None,
    timestamp: int | None = None,
    root_id: str | None = None,
    file_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create base post data for Mattermost API.

    Args:
        channel_id: The ID of the channel to post in
        message_content: The content of the message
        user_id: The ID of the user posting (optional, for admin posting)
        timestamp: Custom timestamp for the message (optional)
        root_id: ID of the root post for threaded replies (optional)
        file_ids: List of file IDs for attachments (optional)

    Returns:
        Dictionary containing post data for Mattermost API
    """
    post_data = {
        "channel_id": channel_id,
        "message": message_content,
    }

    # Add user_id if provided (for admin posting)
    if user_id:
        post_data["user_id"] = user_id

    # Add timestamp if provided, otherwise use current time
    if timestamp:
        post_data["create_at"] = timestamp
    else:
        post_data["create_at"] = int(datetime.datetime.now().timestamp() * 1000)

    # Add root_id for threaded replies
    if root_id:
        post_data["root_id"] = root_id

    # Add file IDs for attachments
    if file_ids:
        post_data["file_ids"] = file_ids

    return post_data
