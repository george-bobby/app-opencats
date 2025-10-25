from pydantic import BaseModel, Field


class PositionResponse(BaseModel):
    positions: list[str] = Field(
        description="""
        A list of realistic job positions for a US-based SME company.
        Should include various departments: Product, Engineering, Marketing, Operations, HR, IT, Leadership.
        Mix of junior to senior positions.
        """,
        examples=[["Software Engineer", "Product Manager", "Marketing Specialist", "HR Manager"]],
    )


class UserForGeneration(BaseModel):
    email: str = Field(
        description="""
        The email address of the user.
        Should be a valid email format and follow company naming convention.
        The domain must be vertexon.com
        Should be unique across the system.
        """,
    )
    username: str = Field(
        description="""
        The username for the user account.
        Should be lowercase, no spaces, and follow the pattern: firstname.lastname
        """,
        examples=["john.doe", "sarah.wilson"],
    )
    first_name: str = Field(
        description="""
        The first name of the user.
        """,
        examples=["John", "Sarah"],
    )
    last_name: str = Field(
        description="""
        The last name of the user.
        """,
        examples=["Doe", "Wilson"],
    )
    position: str = Field(
        description="""
        The job position or title of the user.
        Should be realistic for a US-based SME company.
        """,
        examples=["Software Engineer", "Product Manager", "DevOps Engineer", "UX Designer", "Marketing Specialist", "HR Manager", "System Administrator"],
    )
    roles: str = Field(
        description="""
        The user roles in the system.
        Should be one of: system_user system_admin, system_user
        """,
        examples=["system_user", "system_user system_admin"],
    )


class UserForStorage(BaseModel):
    email: str
    username: str
    first_name: str
    last_name: str
    nickname: str
    position: str
    roles: str
    gender: str
    team_channels: dict[str, list[str]] = Field(default_factory=dict, description="Team-specific channel assignments. Format: {'team_name': ['channel1', 'channel2']}")


class UserResponse(BaseModel):
    users: list[UserForGeneration] = Field(
        description="""
            A list of users for the Mattermost system.
            Should include a diverse mix of roles, positions, and genders.
        """
    )


class ChannelMember(BaseModel):
    user_id: int = Field(
        description="The ID of the user to assign to the channel. MUST be from the provided valid user ID list.",
        gt=0,  # Must be positive integer
    )
    role: str = Field(
        description="The role of the user in the channel: 'member' or 'admin'",
        pattern="^(member|admin)$",  # Strict validation
        examples=["member", "admin"],
    )


class ChannelAssignment(BaseModel):
    channel_name: str = Field(description="The name of the channel to assign users to")
    members: list[ChannelMember] = Field(description="List of users to assign to this channel with their roles")


class ChannelAssignmentResponse(BaseModel):
    channel_assignments: list[ChannelAssignment] = Field(
        description="""
        List of channel assignments. For each channel, specify which users should be members
        and what role they should have (member or admin).
        
        Consider the user's position, seniority, and relevance to the channel topic.
        Ensure realistic assignments - don't put everyone in every channel.
        """
    )
