from pydantic import BaseModel, Field


class Project(BaseModel):
    """A project in the Odoo Project system."""

    name: str = Field(
        description="""
            The name of the project.
            It should be concise and descriptive.
            No more than 5 words
        """,
    )
    customer: str = Field(
        description="""
            The customer or client for the project.
            It should be a valid SME company name.
            The company should be realistic and could exist in USA
        """,
    )
    tags: list[str] = Field(
        description="""List of tags associated with the project.""",
    )
    date_start: str = Field(
        description="""
            The start date of the project in YYYY-MM-DD format.
            It should be distributed evenly between 2024-01-01 and 2025-12-31.
        """,
    )
    date_end: str = Field(
        description="""
            The end date of the project in YYYY-MM-DD format.
            It should be after the start date.
            It should be a realistic duration based on the project name.
        """,
    )
    description: str = Field(
        description="""
            A brief description of the project.
            No more than 12 words
        """,
    )


class ProjectResponse(BaseModel):
    projects: list[Project] = Field(description="A list of generated projects.")
