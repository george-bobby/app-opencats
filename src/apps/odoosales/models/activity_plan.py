from typing import Literal

from pydantic import BaseModel, Field


class ActivityPlanLine(BaseModel):
    activity_type_name: Literal["Call", "Email", "Meeting", "Upload Document"] = Field(
        description="""
            The type of activity to be performed.
            Must be one of the following: 'Call', 'Email', 'Meeting', 'Upload Document'.
            This field represents the nature of the activity in the sales process.
            For example, 'Call' for a phone call, 'Email' for sending an email
            It should be unique for each activity line within the plan.
        """
    )
    summary: str
    delay_count: int
    interval_type: Literal["days", "weeks", "months"]


class ActivityPlan(BaseModel):
    name: str
    activity_plan_lines: list[ActivityPlanLine] = Field(
        description="""
            A list of activity lines that make up the activity plan.
            Each activity line should have a unique activity type name and a summary.
            The sequence of activity lines should represent a logical sales process.
        """
    )


class ActivityPlanResponse(BaseModel):
    activity_plans: list[ActivityPlan] = Field(description="A list of generated activity plans.")
