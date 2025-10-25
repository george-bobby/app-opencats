from pydantic import BaseModel, Field


class SaleTeam(BaseModel):
    name: str = Field(
        description="""
            Name of the sales team.
            It should be a descriptive title that summarizes the team's focus or objectives.
            Example: "East Coast Team", "West Coast Team", "SMB Team", etc.
        """
    )
    alias_name: str = Field(
        description="""
            Alias name for the sales team.
            This is an optional field that can be used to provide an alternative name or identifier for the team.
            Example: "eastcoast", "westcoast", "smb", etc.
        """,
    )
    leader: str = Field(
        description="""
            Get from the list of users.
            Name of the team leader. 
            This should be a unique name from the list of users.
        """,
    )
    members: list[str] = Field(
        description="""
            Get from the list of users.
            List of team members' names. 
            There should be at least 3 members, and the leader's name should not be repeated in this list.
        """,
        min_items=3,
    )


class SaleTeamResponse(BaseModel):
    sale_teams: list[SaleTeam] = Field(
        description="List of generated sale teams.",
        default_factory=list,
    )
