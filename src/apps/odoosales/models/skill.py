from typing import Literal

from pydantic import BaseModel, Field

from apps.odoosales.config.settings import settings


class Skill(BaseModel):
    """A skill of the Odoo HR system."""

    name: str = Field(
        description=f"""
            The name of the skill.
            This should be a descriptive name that clearly identifies the skill.
            It should be realistic and could exist in a US-based company in {settings.DATA_THEME_SUBJECT}.
        """,
    )
    skill_type: Literal["hard", "soft", "language"] = Field(
        description="""
            The type of the skill (hard, soft, or language).
            Hard skills are specific, teachable abilities or knowledge sets.
            Soft skills are interpersonal or people skills.
            Language skills refer to proficiency in a specific language (only English).
        """,
    )


class SkillResponse(BaseModel):
    skills: list[Skill] = Field(description="A list of generated skills.")
