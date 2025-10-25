from typing import Literal

from pydantic import BaseModel, Field


class SubTask(BaseModel):
    """A subtask within a task."""

    name: str = Field(
        description="""
            The name of the subtask. 
            It should be concise and descriptive.
            It should be related to the parent task.
            No more than 5 words
        """,
    )
    description: str = Field(
        description="A very brief description of the subtask.",
    )
    date_deadline: str = Field(
        description="""
            The deadline date of the subtask in YYYY-MM-DD format.
            It should be realistic and within the same timeframe as the parent task.
        """,
    )
    stage: str = Field(
        description="""
            Get from provided list of task stages.
            Should be distributed evenly across stages
            The current stage of the subtask.
        """,
    )
    tags: list[str] = Field(
        description="""
            List of tags associated with the subtask.
            Tags should be relevant to the subtask and help categorize it.
            Each subtask should have at least 2 tags.
        """,
    )


class Blocker(BaseModel):
    """A blocker that prevents a task from being completed."""

    name: str = Field(
        description="""
            The name of the blocker.
            It should be concise and descriptive.
            No more than 5 words
        """,
    )
    description: str = Field(
        description="A very brief description of the blocker.",
    )
    stage: str = Field(
        description="""
            Get from provided list of task stages.
            Should be distributed evenly across stages
            The current stage of the blocker.
        """,
    )
    date_deadline: str = Field(
        description="""
            The deadline date of the blocker in YYYY-MM-DD format.
            It should be realistic and within the same timeframe as the parent task.
        """,
    )
    tags: list[str] = Field(
        description="""
            List of tags associated with the blocker.
            Tags should be relevant to the blocker and help categorize it.
            Each blocker should have at least 2 tags.
        """,
    )


class Task(BaseModel):
    """A task in the Odoo Project system."""

    name: str = Field(
        description="""
            The name of the task.
            It should be concise and descriptive.
            No more than 5 words
        """,
    )
    project: str = Field(
        description="""
            Get from provided list of projects
            The name of the project this task belongs to.
            The project should be relevant to the task.
        """,
    )
    stage: str = Field(
        description="""
            Get from provided list of task stages.
            Should be distributed evenly across stages
            The current stage of the task.
        """,
    )
    description: str = Field(
        description="""
            A brief description of the task.
            No more than 12 words
        """,
    )
    priority: Literal["0", "1"] = Field(
        description="""
            The priority level of the task.
            It should be distributed evenly between '0', '1'.
            '0' is low priority, '1' is high priority
        """,
    )
    date_deadline: str = Field(
        description="""The deadline date of the task in YYYY-MM-DD format.""",
    )
    tags: list[str] = Field(
        description="""
            List of tags associated with the task.
            Tags should be relevant to the task and help categorize it.
            Each task should have at least 2 tags.
        """,
    )
    next_activity: str = Field(
        description="""
            Get from provided list of activity types.
            The type of next activity planned for this task.
        """,
    )
    children: list[SubTask] = Field(
        description="""
            List of child tasks.
            The child tasks should be related to the parent task.
            Each task should at least 5 child tasks.
            Child tasks should be unique and not repeat the same name across parent tasks.
        """,
    )
    blockers: list[Blocker] | None = Field(
        default=None,
        description="""
            List of tasks that are blocking this task.
            The blockers should be related to the task.
            If the task is simple, it should have no blockers.
            If the task is complex, it should have at least 2 blockers.
        """,
    )
    email_cc: str = Field(
        description="""
            Email addresses that were in the CC of the incoming emails from this task and that are not currently linked to an existing customer.
            The domain must be gmail.com or outlook.com
            The name should be a valid email address and a human name.
            The email should be unique for each task.
            The format should be: firstname.lastname.birth_year@(gmail|outlook).com

            EXAMPLE: john.doe.1997@gmail.com, jane.doe.1995@outlook.com, etc.
        """,
    )


class TaskResponse(BaseModel):
    tasks: list[Task] = Field(description="A list of generated tasks.")
