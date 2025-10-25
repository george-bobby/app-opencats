from pydantic import BaseModel, Field


class WorkCenter(BaseModel):
    """
    Represents a work center in a manufacturing or production environment.
    A work center is a specific area where production tasks are performed.
    """

    name: str = Field(
        description="The human-readable name of the work center, e.g., 'Cutting & Prep Station'.",
    )
    code: str = Field(description="A short, unique code for easy reference, e.g., 'CUT_PREP'.")
    time_efficiency: float = Field(
        description="The expected productivity as a percentage. 100 means it operates at its theoretical maximum speed.",
    )
    default_capacity: float = Field(
        description="The number of operations that can be performed simultaneously. A value of 1 means it handles one task at a time.",
    )
    oee_target: float = Field(
        description="""
            The target for Overall Equipment Effectiveness (OEE) as a percentage. 
            OEE is a key performance indicator measuring manufacturing productivity. 
            An 85% target is considered world-class.
        """,
    )
    costs_hour: float = Field(description="The operational cost per hour to run this work center.")
    note: str = Field(
        description="A free-text field for additional details or a description of the work center's function.",
    )


class WorkCenterResponse(BaseModel):
    work_centers: list[WorkCenter] = Field(
        description="A list of work centers, each representing a specific area where production tasks are performed.",
    )
