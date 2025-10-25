"""Shared message processing logic for Mattermost."""

from .attachments import handle_file_attachments
from .concurrent_processing import (
    ConcurrentTaskManager,
    gather_with_limit,
    process_batches_concurrently,
    process_items_with_semaphore,
)
from .insertion import insert_thread_messages
from .llm_generation import (
    create_attachment_instructions,
    create_business_theme_context,
    create_current_date_context,
    create_markdown_guidelines,
    create_timestamp_context,
    create_user_directory_context,
    generate_thread_with_llm,
)
from .message_processing import (
    apply_timestamps_to_messages,
    convert_llm_to_complete_messages,
    prepare_messages_for_json,
    prepare_threads_for_json,
)
from .post_features import handle_message_pinning, handle_message_reactions
from .post_utils import create_base_post_data
from .thread_utils import (
    create_message_context_prompt,
    create_thread_context_prompt,
    set_probabilistic_message_attributes,
    set_probabilistic_thread_attributes,
)
from .timestamp_generation import (
    generate_conversation_timestamps,
    generate_thread_message_timestamps,
    generate_thread_timestamps,
)


__all__ = [
    # Core utilities
    "create_base_post_data",
    "handle_file_attachments",
    "handle_message_pinning",
    "handle_message_reactions",
    "insert_thread_messages",
    # Thread utilities
    "create_message_context_prompt",
    "create_thread_context_prompt",
    "set_probabilistic_message_attributes",
    "set_probabilistic_thread_attributes",
    # LLM generation
    "create_attachment_instructions",
    "create_business_theme_context",
    "create_current_date_context",
    "create_markdown_guidelines",
    "create_timestamp_context",
    "create_user_directory_context",
    "generate_thread_with_llm",
    # Message processing
    "convert_llm_to_complete_messages",
    "apply_timestamps_to_messages",
    "prepare_messages_for_json",
    "prepare_threads_for_json",
    # Timestamp generation
    "generate_conversation_timestamps",
    "generate_thread_message_timestamps",
    "generate_thread_timestamps",
    # Concurrent processing
    "ConcurrentTaskManager",
    "gather_with_limit",
    "process_batches_concurrently",
    "process_items_with_semaphore",
]
