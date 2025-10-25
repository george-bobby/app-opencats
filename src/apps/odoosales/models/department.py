from pydantic import BaseModel, Field

from apps.odoosales.config.settings import settings
from apps.odoosales.models.emp import Employee


class Department(BaseModel):
    name: str = Field(
        description=f"""
            The name of the department within the organization.
            It should be descriptive of the department's function or focus.
            It should be unique within the organization.
            It should be realistic and could exist in a US-based company in {settings.DATA_THEME_SUBJECT}.
        """
    )
    manager: Employee = Field(
        description="""
            The employee who is the manager of this department.
            This person is responsible for overseeing the department's operations.
        """
    )


class DepartmentResponse(BaseModel):
    departments: list[Department] = Field(
        description="""
            A list of departments within the organization.
            Each department should have a unique name and a manager.
            The employees in each department should be diverse in terms of roles and responsibilities.
        """
    )
