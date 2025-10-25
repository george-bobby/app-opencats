from enum import Enum


class MailModelName(Enum):
    MAIL_ACTIVITY_TYPE = "mail.activity.type"
    MAIL_ACTIVITY_PLAN = "mail.activity.plan"
    MAIL_ACTIVITY_PLAN_TEMPLATE = "mail.activity.plan.template"
    MAIL_ACTIVITY = "mail.activity"
    MAIL_MESSAGE = "mail.message"
    MAIL_FOLLOWERS = "mail.followers"
    MAIL_ACTIVITY_SCHEDULE = "mail.activity.schedule"


class ProjectModelName(Enum):
    PROJECT_PROJECT = "project.project"
    PROJECT_TASK = "project.task"
    PROJECT_TASK_TYPE = "project.task.type"
    PROJECT_TAGS = "project.tags"
    PROJECT_PROJECT_STAGE = "project.project.stage"


class ResModelName(Enum):
    RES_CONFIG_SETTINGS = "res.config.settings"
    RES_GROUP = "res.groups"
    RES_USERS = "res.users"
    RES_PARTNER = "res.partner"
    RES_COMPANY = "res.company"
    RES_INDUSTRY = "res.partner.industry"
    RES_CATEGORY = "res.partner.category"
    RES_COUNTRY = "res.country"
    RES_COUNTRY_STATE = "res.country.state"


DEFAULT_ADDRESS_ID = 1
DEFAULT_COUNTRY_ID = 233  # United States
DEFAULT_ADMIN_USER_ID = 2
DEFAULT_EMPLOYEE_ID = 1
DEFAULT_COMPANY_ID = 1

TASK_STATES = ["01_in_progress", "02_changes_requested", "03_approved", "1_done", "1_canceled", "04_waiting_normal"]
PROJECT_STATUS = ["on_track", "at_risk", "off_track", "on_hold", "to_define", "done"]
