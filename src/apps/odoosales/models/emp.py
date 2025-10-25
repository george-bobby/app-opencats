from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from apps.odoosales.config.settings import settings


df_job_positions = pd.read_json(settings.DATA_PATH.joinpath("job_positions.json"))
df_departments = pd.read_json(settings.DATA_PATH.joinpath("departments.json"))


class PrivateAddress(BaseModel):
    street: str = Field(
        description="""
            The street address of the employee's private residence.
            This should include the house number and street name.
        """
    )
    city: str = Field(
        description="""
            The city where the employee's private residence is located.
            This is a major administrative division of a state.
        """
    )
    state: str = Field(
        description="""
            The state or province of the employee's private residence.
            This is a major administrative division of a country in US.
            It should be a complete state name, such as 'California' or 'New York'.
            
        """
    )
    zip_code: str = Field(
        description="""
            The postal code or ZIP code of the employee's private residence.
            This helps in mail delivery and location identification.
        """
    )


class Education(BaseModel):
    certificate: Literal["graduate", "bachelor", "other"] = Field(
        description="""
            The highest level of education certificate obtained by the employee.
            It should be relevant to the job positions and title
        """
    )
    study_field: str = Field(
        description="""
            The major or field of study pursued by the employee.
            This indicates the employee's area of academic specialization.
        """
    )
    study_school: str = Field(
        description="""
            The name of the educational institution where the employee studied.
            This is the school, college, or university they attended.
        """
    )


class ResumeLine(BaseModel):
    name: str = Field(
        description="""
            The name of the company or institution related to the resume line.
            This could be a previous employer or an educational institution.
        """
    )
    resume_type: str = Field(
        description="""
            The type of the resume line, such as 'Experience' or 'Education'.
            This helps to categorize the information on the resume.
        """
    )
    date_start: str = Field(
        description="""
            The start date of the experience or education.
            This marks the beginning of the period.
        """
    )
    date_end: str | None = Field(
        description="""
            The end date of the experience or education.
            This can be empty if the experience is ongoing.
        """
    )
    description: str = Field(
        description="""
            A detailed description of the role, responsibilities, or achievements.
            This provides more context about the resume line.
        """
    )


class Employee(BaseModel):
    name: str = Field(
        description="""
            The full name of the employee.
            This should include their first name and last name.
            It should be unique across the system.
        """
    )
    department: str | None = Field(
        default=None,
        description=f"""
            The department where the employee works.
            Get from provided department data: {df_departments["name"].to_list()}.
            This indicates the functional area of the employee's work.
            If job position is C-level, it should be None.
        """,
    )
    job_title: str = Field(
        description="""
            The official job title of the employee within the organization.
            This describes their position and role.
            It should be relevant to the employee's department and responsibilities.
        """
    )
    work_email: str = Field(
        description="""
            The corporate email address of the employee.
            This is used for all official communication.
            It should include the department of the employee.
            It should only contains name part, not including domain.
            For example: 
            - dangnguyen.it, not dangnguyen.it@gmail.com
            - johndoe.sales, not johndoe.sales@gmail.com
            - janedoe.marketing, not janedoe.marketing@gmail.com
        """
    )
    job_position: str = Field(
        description=f"""
            Get from provided job positions data: {df_job_positions["name"].to_list()}.
            It should be relevant to the employee's role, department and responsibilities.
        """
    )
    resume_lines: list[ResumeLine] = Field(
        description="""
            A list of the employee's resume lines.
            This includes their work experience and educational background.
            There should be at least 3 resume lines for each employee including their current position and 1 education.
        """
    )
    skills: list[str] = Field(
        description="""
            A list of skills possessed by the employee.
            These skills should be relevant to their job position.
            Each skill should be realistic and applicable to a US-based SME in {settings.DATA_THEME_SUBJECT}.
            There should be at least 5 skills for each employee.
        """
    )
    private_address: PrivateAddress = Field(
        description="""
            The private residential address of the employee.
            This information is kept confidential.
        """
    )
    private_email: str = Field(
        description="""
            The personal email address of the employee.
            This is used for non-work-related communication.
            The domain must be gmail.com or outlook.com
        """
    )
    private_car_plate: str = Field(
        description="""
            The license plate number of the employee's private car.
            This may be required for parking arrangements.
        """
    )
    gender: str = Field(
        description="""
            The gender of the employee.
            This can be 'male', 'female', or 'other'.
        """
    )
    passport_id: str = Field(
        description="""
            The employee's passport number.
            This is a unique identifier for international travel.
        """
    )
    ssnid: str = Field(
        description="""
            The employee's Social Security Number or equivalent national identification number.
            This is a sensitive piece of information.
        """
    )
    identification_id: str = Field(
        description="""
            An alternative identification number for the employee.
            This could be a national ID card number.
        """
    )
    place_of_birth: str = Field(
        description="""
            The city and country where the employee was born.
            This is part of their personal information.
        """
    )
    education: Education = Field(
        description="""
            Details about the employee's educational qualifications.
            This includes their degree, field of study, and institution.
        """
    )
    categories: list[str] = Field(
        description="""
            A list of categories or tags associated with the employee.
            This can be used for filtering and reporting.
        """
    )


class EmployeeResponse(BaseModel):
    employees: list[Employee] = Field(
        description="""
            A list of all employees within the organization.
            Each employee has detailed information such as name, job title, and contact information.
        """
    )


class CLevelResponse(BaseModel):
    ceo: Employee = Field(
        description="""
            The Chief Executive Officer of the organization.
            This is the highest-ranking executive in the company.
            CEO does not have a department.
        """
    )
    coo: Employee = Field(
        description="""
            The Chief Operating Officer of the organization.
            This executive is responsible for the day-to-day operations of the company.
            COO does not have a department.
        """
    )
