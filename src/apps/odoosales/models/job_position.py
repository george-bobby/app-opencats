from pydantic import BaseModel, Field


class JobPosition(BaseModel):
    """A job position for HR recruitment."""

    name: str = Field(
        description="""The name/title of the job position.""",
    )
    description: str = Field(
        description="""A detailed description of the job position and responsibilities.""",
    )
    department: str = Field(
        description="""The department this job position belongs to.""",
    )
    skills: list[str] = Field(
        description="""A list of required skills for this position.""",
    )
    no_of_recruitment: int = Field(
        description="""
            The number of positions available for recruitment.
            For manager positions or C levels, it should be 1.
            For other positions, it should be more than 2.    
        """,
        ge=1,
    )


class JobPositionResponse(BaseModel):
    """Response model for job position generation."""

    job_positions: list[JobPosition]
