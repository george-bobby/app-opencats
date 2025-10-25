from enum import Enum


class HRModelName(Enum):
    HR_LEAVE_ACCRUAL_PLAN = "hr.leave.accrual.plan"
    HR_LEAVE_ACCRUAL_LEVEL = "hr.leave.accrual.level"
    HR_CANDIDATE = "hr.candidate"
    HR_CANDIDATE_SKILL = "hr.candidate.skill"
    HR_RECRUITMENT_DEGREE = "hr.recruitment.degree"
    HR_SKILL_LEVEL = "hr.skill.level"
    HR_SKILL = "hr.skill"
    HR_SKILL_TYPE = "hr.skill.type"
    HR_EMPLOYEE = "hr.employee"
    HR_DEPARTMENT = "hr.department"
    HR_JOB = "hr.job"
    HR_CONTRACT_TYPE = "hr.contract.type"
    HR_LEAVE_TYPE = "hr.leave.type"
    RESOURCE_CALENDAR = "resource.calendar"
    RESOURCE_CALENDAR_ATTENDANCE = "resource.calendar.attendance"
    HR_WORK_LOCATION = "hr.work.location"
    HR_LEAVE = "hr.leave"
    HR_LEAVE_ALLOCATION = "hr.leave.allocation"
    HR_APP = "hr.applicant"
    HR_RECRUITMENT_STAGE = "hr.recruitment.stage"
    HR_EMPLOYEE_SKILL = "hr.employee.skill"
    HR_ATTENDANCE = "hr.attendance"
    HR_RESUME_LINE_TYPE = "hr.resume.line.type"
    HR_RESUME_LINE = "hr.resume.line"
    HR_EMPLOYEE_CATEGORY = "hr.employee.category"


class MiscEnum(Enum):
    IR_MODULE_CATEGORY = "ir.module.category"


class ResModelName(Enum):
    PARTNER_INDUSTRY = "res.partner.industry"
    USER = "res.users"
    GROUP = "res.groups"
    PARTNER = "res.partner"
    COUNTRY = "res.country"
    COUNTRY_STATE = "res.country.state"
    CURRENCY = "res.currency"
    BANK = "res.partner.bank"


DEFAULT_ADDRESS_ID = 1
DEFAULT_COUNTRY_ID = 233  # United States
DEFAULT_ADMIN_USER_ID = 2
DEFAULT_EMPLOYEE_ID = 1
