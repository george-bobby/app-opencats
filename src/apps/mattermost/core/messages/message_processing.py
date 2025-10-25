"""Shared message processing utilities."""

from apps.mattermost.models.message import Message, Thread, ThreadForGeneration


def convert_llm_to_complete_messages(llm_response: ThreadForGeneration, thread_template: Thread) -> list[Message]:
    """
    Convert LLM-generated messages to complete Message objects with pre-generated attributes.

    Args:
        llm_response: LLM-generated thread response (includes from_user chosen by LLM)
        thread_template: Thread template with probabilistic attributes

    Returns:
        List of complete Message objects
    """
    complete_messages = []

    for msg_idx, llm_message in enumerate(llm_response.messages):
        if msg_idx >= len(thread_template.messages):
            break

        # Use the pre-generated message attributes from template
        template_message = thread_template.messages[msg_idx]

        # Use the from_user chosen by the LLM
        from_user_id = llm_message.from_user

        # Create complete Message with both LLM content and probabilistic attributes
        complete_message = Message(
            from_user=from_user_id,
            content=llm_message.content,
            is_pinned=template_message.is_pinned,
            has_reactions=template_message.has_reactions,
            timestamp=getattr(template_message, "timestamp", None),
            attachment_filenames=llm_message.attachment_filenames if llm_message.attachment_filenames else [],
        )
        complete_messages.append(complete_message)

    return complete_messages


def apply_timestamps_to_messages(messages: list[Message], timestamps: list[int]) -> list[Message]:
    """
    Apply timestamps to messages and sort chronologically.

    Args:
        messages: List of Message objects
        timestamps: List of timestamps in milliseconds

    Returns:
        List of messages with timestamps applied, sorted chronologically
    """
    # Apply timestamps
    for i, message in enumerate(messages):
        if i < len(timestamps):
            message.timestamp = timestamps[i]

    # Sort by timestamp to ensure chronological order
    messages.sort(key=lambda msg: getattr(msg, "timestamp", 0))

    return messages


def prepare_messages_for_json(messages_data: list[dict]) -> list[dict]:
    """
    Prepare message data for JSON serialization with timestamp validation.

    Args:
        messages_data: List of message dictionaries

    Returns:
        List of message dictionaries with validated timestamps
    """
    import datetime

    for message_dict in messages_data:
        # Ensure timestamp is included
        if "timestamp" not in message_dict or message_dict["timestamp"] is None:
            message_dict["timestamp"] = int(datetime.datetime.now().timestamp() * 1000)

        # Handle related messages if they exist (for backward compatibility)
        for related_dict in message_dict.get("related_messages", []):
            if "timestamp" not in related_dict or related_dict["timestamp"] is None:
                related_dict["timestamp"] = int(datetime.datetime.now().timestamp() * 1000)

    return messages_data


def prepare_threads_for_json(threads: list[Thread]) -> list[dict]:
    """
    Prepare thread data for JSON serialization.

    Args:
        threads: List of Thread objects

    Returns:
        List of thread dictionaries ready for JSON serialization
    """
    threads_data = []

    for thread in threads:
        thread_dict = thread.model_dump()

        # Process messages within the thread
        messages_data = thread_dict.get("messages", [])
        thread_dict["messages"] = prepare_messages_for_json(messages_data)

        threads_data.append(thread_dict)

    return threads_data
