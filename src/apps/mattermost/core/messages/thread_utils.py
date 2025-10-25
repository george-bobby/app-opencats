"""Utilities for creating and managing message threads."""

import random

from apps.mattermost.models.message import Message, Thread
from apps.mattermost.utils.constants import CHANNEL_MESSAGE_REACTION_PROBABILITY, DM_MESSAGE_REACTION_PROBABILITY


def set_probabilistic_thread_attributes(
    threads: list[Thread],
    context_type: str = "channel",
    attachment_probability: int | None = None,
) -> list[Thread]:
    """
    Set probabilistic attributes for threads (pinning, reactions, threading, attachments).

    Args:
        threads: List of Thread objects to modify
        context_type: "channel" or "dm" to determine probability rates
        attachment_probability: Override for attachment probability (percentage)

    Returns:
        List of threads with probabilistic attributes set
    """
    # Determine reaction probability based on context
    if context_type == "dm":
        reaction_probability = DM_MESSAGE_REACTION_PROBABILITY / 100
        pin_probability = 0.02  # 5% for DMs (more personal)
    else:  # channel
        reaction_probability = CHANNEL_MESSAGE_REACTION_PROBABILITY / 100
        pin_probability = 0.05  # 10% for channels

    for thread in threads:
        # Set thread-level threading behavior (30% chance for threaded replies)
        thread.has_root_message = random.random() < 0.3

        # Set thread-level attachment behavior if specified
        if attachment_probability is not None:
            thread.should_have_attachments = random.random() < (attachment_probability / 100)

        # Set message-level attributes
        for message in thread.messages:
            # Set pinning probability
            message.is_pinned = random.random() < pin_probability

            # Set reaction probability
            message.has_reactions = random.random() < reaction_probability

            # Initialize empty attachment filenames (LLM will fill based on should_have_attachments)
            if not hasattr(message, "attachment_filenames") or message.attachment_filenames is None:
                message.attachment_filenames = []

    return threads


def set_probabilistic_message_attributes(
    messages: list[Message],
    context_type: str = "channel",
) -> list[Message]:
    """
    Set probabilistic attributes for individual messages (backward compatibility).

    Args:
        messages: List of Message objects to modify
        context_type: "channel" or "dm" to determine probability rates

    Returns:
        List of messages with probabilistic attributes set
    """
    # Determine probability based on context
    if context_type == "dm":
        reaction_probability = DM_MESSAGE_REACTION_PROBABILITY / 100
        pin_probability = 0.05  # 5% for DMs
    else:  # channel
        reaction_probability = CHANNEL_MESSAGE_REACTION_PROBABILITY / 100
        pin_probability = 0.10  # 10% for channels

    for message in messages:
        # Set pinning probability
        message.is_pinned = random.random() < pin_probability

        # Set reaction probability
        message.has_reactions = random.random() < reaction_probability

        # Initialize empty attachment filenames
        if not hasattr(message, "attachment_filenames") or message.attachment_filenames is None:
            message.attachment_filenames = []

    return messages


def create_thread_context_prompt(threads: list[Thread]) -> str:
    """Create context prompt with probabilistic thread and message attributes."""
    context_lines = []

    for i, thread in enumerate(threads, 1):
        thread_type = "threaded replies" if thread.has_root_message else "standalone messages"
        attachment_info = ""
        if hasattr(thread, "should_have_attachments") and thread.should_have_attachments is not None:
            attachment_info = " with attachments" if thread.should_have_attachments else " without attachments"

        context_lines.append(f"Thread {i}: {thread_type}{attachment_info}")

        for j, message in enumerate(thread.messages, 1):
            pin_status = "PINNED" if message.is_pinned else "not pinned"
            reaction_status = "MUST have reactions" if message.has_reactions else "optional reactions"
            context_lines.append(f"  Message {i}.{j}: {pin_status}, {reaction_status}")

    return "\n".join(context_lines)


def create_message_context_prompt(messages: list[Message]) -> str:
    """Create context prompt with probabilistic message attributes (backward compatibility)."""
    context_lines = []
    for i, message in enumerate(messages, 1):
        pin_status = "PINNED" if message.is_pinned else "not pinned"
        reaction_status = "MUST have reactions" if message.has_reactions else "optional reactions"
        context_lines.append(f"Message {i}: {pin_status}, {reaction_status}")

    return "\n".join(context_lines)
