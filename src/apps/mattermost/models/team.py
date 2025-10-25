from typing import Literal

from pydantic import BaseModel, Field


class Channel(BaseModel):
    name: str = Field(
        description="""
        The name of the channel.
        It must be 2 or more lowercase alphanumeric characters.
        If there are 2 characters, separated them with -
        """,
        examples=["product-roadmap", "feature-specs"],
    )
    display_name: str = Field(
        description="""
        The display name of the channel.
        """,
        examples=["Product Roadmap", "Feature Specifications"],
    )
    description: str = Field(
        description="""
        The description of the channel.
        """,
        examples=[
            "Product roadmap discussions and planning",
            "Private channel for detailed feature specifications",
        ],
    )
    channel_type: Literal["O", "P"] = Field(
        description="""
            The type of the channel.
            It must be either 'O' for open or 'P' for private.
        """,
        examples=["O", "P"],
    )


class Team(BaseModel):
    name: str = Field(
        description="""
            Name of the team
            It should represent for department name
            It must be 2 or more lowercase alphanumeric characters.
            If there are 2 characters, separated them with -
            
            EXAMPLE: product, development, marketing, operations, hr
        """
    )
    display_name: str = Field(
        description="""
            The internal name for management
        """
    )
    channels: list[Channel] = Field(
        description="""
            A list of channels for each team
            There should be 5-7 channels for each team
        """
    )


class TeamResponse(BaseModel):
    teams: list[Team] = Field(
        description="""
            A list of teams
            There should be at least 5 teams
        """
    )
