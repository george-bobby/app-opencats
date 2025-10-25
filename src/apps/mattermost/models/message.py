from pydantic import BaseModel, Field


# ============================================================================
# Models for LLM Generation (clean, without programmatic fields)
# ============================================================================


class MessageForGeneration(BaseModel):
    from_user: int = Field(
        description="""
        The ID of the user who sent this message.
        Must be a valid user ID from the provided participants list.
        Choose the appropriate user based on the conversation flow and context.
        """,
        examples=[2, 5, 8],
    )
    content: str = Field(
        description="""
        The content of the message.
        Should be realistic work-related content appropriate for the channel.
        Should be concise and straight to the point.
        Should be appropriate for a professional setting.
        No more than 2-3 sentences.
        """,
    )
    attachment_filenames: list[str] = Field(
        description="""
        Optional list of filenames for file attachments if this message naturally needs them.
        Only include if the message content specifically references sharing files.
        Should be realistic filenames like: ['budget_q3.xlsx'], ['meeting_notes.md', 'agenda.pdf'], ['server_logs.txt']
        Leave empty list if no attachments are needed.
        """,
        default_factory=list,
    )


class ThreadForGeneration(BaseModel):
    messages: list[MessageForGeneration] = Field(
        description="""
        List of related messages in this conversation thread.
        Messages in the same thread are related to each other.
        """,
    )


class DirectMessagesForGeneration(BaseModel):
    threads: list[ThreadForGeneration] = Field(
        description="""
        List of conversation threads for this direct message conversation.
        Each thread contains related messages that form a coherent conversation.
        """,
    )


class DirectMessageResponseForGeneration(BaseModel):
    messages: list[DirectMessagesForGeneration] = Field(
        description="""
        A list of direct messages for the Mattermost system.
        Should cover all direct messages between members in the same channel teams.json.
        """
    )


class ChannelMessageResponseForGeneration(BaseModel):
    messages: list[MessageForGeneration] = Field(
        description="""
        List of messages for this channel.
        """,
    )


class ChannelThreadsForGeneration(BaseModel):
    threads: list[ThreadForGeneration] = Field(
        description="""
        List of conversation threads for this channel.
        Each thread represents a focused discussion topic with multiple related messages.
        """,
    )


# ============================================================================
# Complete Data Models (with all fields including programmatic ones)
# ============================================================================


class Message(BaseModel):
    from_user: int = Field(
        description="""
        Get from provided list of users.
        The ID of the user who sent this message.
        Must be a valid user ID from the users list.
        Messages must be sent by users in the same channel.
        """,
        examples=[2, 5, 8],
    )
    content: str = Field(
        description="""
        The content of the message.
        Should be realistic work-related content appropriate for the channel.
        Should be concise and straight to the point.
        Should be appropriate for a professional setting.
        No more than 2-3 sentences.
        """,
    )
    is_pinned: bool | None = Field(
        description="""
        Whether this message is pinned (set probabilistically - 10% chance).
        This will be set programmatically during message generation.
        DO NOT generate this field with LLM - it will be populated by code.
        """,
        default=None,
    )
    has_reactions: bool | None = Field(
        description="""
        Whether this message should have reactions (set probabilistically - 80% chance).
        This will be set programmatically during message generation.
        DO NOT generate this field with LLM - it will be populated by code.
        """,
        default=None,
    )
    timestamp: int | None = Field(
        description="""
        The timestamp when this message was sent (in milliseconds since epoch).
        This will be set programmatically during message generation.
        DO NOT generate this field with LLM - it will be populated by code.
        """,
        default=None,
    )
    attachment_filenames: list[str] = Field(
        description="""
        List of filenames for file attachments if this message has them.
        This will be populated by the LLM when generating message content.
        """,
        default_factory=list,
    )


class Thread(BaseModel):
    messages: list[Message] = Field(
        description="""
        List of related messages in this conversation thread.
        Messages in the same thread are related to each other and form a coherent conversation.
        """,
    )
    has_root_message: bool | None = Field(
        description="""
        Whether messages in this thread should be posted as threaded replies (set probabilistically - 30% chance).
        When True: Messages 2+ are posted as replies to message 1 (with root_id set).
        When False: All messages are posted as separate standalone messages in the channel.
        This will be set programmatically during message generation.
        """,
        default=None,
    )
    should_have_attachments: bool | None = Field(
        description="""
        Whether this thread should include file attachments (set probabilistically - 50% chance).
        When True: LLM will be instructed to include relevant file attachments.
        When False: LLM will be instructed to not include any file attachments.
        This will be set programmatically during message generation.
        """,
        default=None,
    )


class DirectMessages(BaseModel):
    members: list[int] = Field(
        description="""
        Get from provided list of users.
        The user IDs of the members in this direct message conversation.
        Must be valid user IDs from the users list.
        """,
        examples=[2, 5],
    )
    threads: list[Thread] = Field(
        description="""
        List of conversation threads for this direct message conversation.
        Each thread contains related messages that form a coherent conversation.
        """,
    )

    def get(self, key: str, default=None):
        return getattr(self, key, default)


class DirectMessageResponse(BaseModel):
    messages: list[DirectMessages] = Field(
        description="""
        A list of direct messages for the Mattermost system.
        Should cover all direct messages between members in the same channel teams.json.
        """
    )


class ChannelMessageResponse(BaseModel):
    messages: list[Message] = Field(
        description="""
        List of messages for this channel.
        """,
    )


class ChannelThreads(BaseModel):
    threads: list[Thread] = Field(
        description="""
        List of conversation threads for this channel.
        Each thread represents a focused discussion topic with multiple related messages.
        """,
    )
