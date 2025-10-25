from pydantic import BaseModel, Field


class Note(BaseModel):
    """A note that can be attached to a sale order."""

    name: str = Field(
        description="""The name of the note.""",
    )
    description: str = Field(
        description="""A detailed description of the note.""",
    )


class NoteResponse(BaseModel):
    notes: list[Note] = Field(description="A list of generated notes.")
