from pydantic import BaseModel, Field


class User(BaseModel):
    """A user of the Odoo Project system."""

    name: str = Field(
        description="""The full name of the user.""",
    )
    email: str = Field(
        description="""
            The email address of the user.
            The domain must be gmail.com or outlook.com
        """,
    )


class UserResponse(BaseModel):
    users: list[User] = Field(description="A list of generated users.")
