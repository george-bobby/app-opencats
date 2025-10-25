"""File attachment handling for Mattermost messages."""

import random
from typing import Any

from apps.mattermost.utils.mattermost import MattermostClient
from common.logger import logger


async def handle_file_attachments(
    message: dict[str, Any],
    channel_id: str,
    client: MattermostClient,
) -> list[str]:
    """
    Handle file attachments for a message.

    Args:
        message: Message data containing attachment_filenames
        channel_id: ID of the channel to upload files to
        client: Authenticated MattermostClient instance

    Returns:
        List of file IDs for successful uploads
    """
    file_ids = []
    attachment_filenames = message.get("attachment_filenames", [])

    for attachment_filename in attachment_filenames:
        try:
            # Generate binary file data directly in memory (a few KB in size)
            file_size = random.randint(2048, 8192)  # 2-8 KB
            file_data = b"\x00" * file_size

            # Upload the file data directly without writing to disk
            file_result = await client.upload_file_data(channel_id, file_data, attachment_filename)

            if file_result and file_result.get("file_infos"):
                file_info = file_result["file_infos"][0]
                file_ids.append(file_info["id"])
                # logger.debug(f"Uploaded file {attachment_filename} to channel {channel_id}")

        except Exception as e:
            logger.debug(f"Failed to upload file {attachment_filename}: {e}")

    return file_ids
