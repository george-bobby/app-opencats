from pydantic import BaseModel, Field


class ActivityLine(BaseModel):
    """An activity line within an activity plan."""

    activity_type: str = Field(
        description="""
            Get from provided list of activity types.
        """,
    )
    summary: str = Field(
        description="""A brief summary of the activity.""",
    )
    assignment: str = Field(
        description="""How the activity should be assigned (e.g., 'ask_at_launch', 'default_user').""",
    )
    interval: int = Field(
        description="""The interval value for the activity timing.""",
    )
    delay_unit: str = Field(
        description="""The unit for the delay (e.g., 'days').""",
    )
    trigger: str = Field(
        description="""When the activity should be triggered (e.g., 'before_plan_date', 'after_plan_date').""",
    )


class ActivityPlan(BaseModel):
    """An activity plan in the Odoo Project system."""

    name: str = Field(
        description="""The name of the activity plan.""",
    )
    model: str = Field(
        description="""The Odoo model this activity plan applies to (e.g., 'project.task', 'project.project').""",
    )
    activity_lines: list[ActivityLine] = Field(
        description="""List of activity lines that make up this plan.""",
    )


class ActivityPlanResponse(BaseModel):
    activity_plans: list[ActivityPlan] = Field(description="A list of generated activity plans.")
