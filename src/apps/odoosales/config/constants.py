from enum import Enum


class IrModelName(Enum):
    IR_MODEL = "ir.model"
    IR_MODEL_FIELDS = "ir.model.fields"
    IR_UI_VIEW = "ir.ui.view"
    IR_UI_MENU = "ir.ui.menu"
    IR_CONFIG_PARAMETER = "ir.config_parameter"
    IR_ATTACHMENT = "ir.attachment"


class CrmModelName(Enum):
    CRM_TEAM = "crm.team"
    CRM_TEAM_MEMBER = "crm.team.member"
    CRM_LEAD = "crm.lead"
    CRM_STAGE = "crm.stage"
    CRM_TAG = "crm.tag"


class MailModelName(Enum):
    MAIL_ACTIVITY_TYPE = "mail.activity.type"
    MAIL_ACTIVITY_PLAN = "mail.activity.plan"
    MAIL_ACTIVITY_PLAN_TEMPLATE = "mail.activity.plan.template"
    MAIL_ACTIVITY = "mail.activity"
    MAIL_MESSAGE = "mail.message"
    MAIL_FOLLOWERS = "mail.followers"


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
    RES_PARTNER_INDUSTRY = "res.partner.industry"
    RES_PARTNER_BANK = "res.partner.bank"
    RES_BANK = "res.bank"


class POSModelName(Enum):
    POS_CONFIG = "pos.config"
    POS_SESSION = "pos.session"
    POS_ORDER = "pos.order"
    POS_PAYMENT_METHOD = "pos.payment.method"
    POS_CATEGORY = "pos.category"
    POS_NOTE = "pos.note"


class ProductModelName(Enum):
    PRODUCT_TEMPLATE = "product.template"
    PRODUCT_PRODUCT = "product.product"
    PRODUCT_CATEGORY = "product.category"
    PRODUCT_ATTRIBUTE = "product.attribute"
    PRODUCT_ATTRIBUTE_VALUE = "product.attribute.value"
    PRODUCT_TAG = "product.tag"
    PRODUCT_PRICELIST = "product.pricelist"
    PRODUCT_PRICELIST_ITEM = "product.pricelist.item"


class AccountModelName(Enum):
    ACCOUNT_JOURNAL = "account.journal"
    ACCOUNT_PAYMENT_TERM = "account.payment.term"
    ACCOUNT_TAX = "account.tax"
    ACCOUNT_INVOICE = "account.move"


class QuotationModelName(Enum):
    QUOTATION_DOCUMENT = "quotation.document"
    QUOTATION_TEMPLATE = "quotation.template"
    QUOTATION_LINE = "quotation.line"


class SaleModelName(Enum):
    SALE_ORDER = "sale.order"
    SALE_ORDER_LINE = "sale.order.line"
    SALE_TAG = "sale.tag"
    SALE_TEAM = "sale.team"
    SALE_REPORT = "sale.report"


class StockModelName(Enum):
    STOCK_PICKING = "stock.picking"
    STOCK_PICKING_TYPE = "stock.picking.type"
    STOCK_MOVE = "stock.move"
    STOCK_WAREHOUSE = "stock.warehouse"
    STOCK_LOCATION = "stock.location"
    STOCK_QUANT = "stock.quant"


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


COMPANY_INDUSTRIES = [
    "Agriculture",
    "Manufacturing",
    "Technology",
    "Healthcare",
    "Finance",
    "Retail",
    "Education",
    "Real Estate",
    "Construction",
    "Hospitality",
    "Transportation",
    "Energy",
    "Telecommunications",
    "Media",
    "Consulting",
    "Automotive",
    "Aerospace",
    "Pharmaceutical",
    "Biotechnology",
    "Chemical",
]

CONTACT_TAGS = [
    "VIP",
    "Prospect",
    "Partner",
    "Investor",
    "Alumni",
    "Newsletter",
    "Event Attendee",
    "Referral",
    "Community Member",
    "Social Media",
    "Industry Expert",
    "Influencer",
    "Brand Ambassador",
    "Advocate",
    "Volunteer",
    "Donor",
    "Sponsor",
    "Consultant",
]

SALE_TEAMS_DATA = [
    {
        "name": "East Coast Team",
        "alias_name": "eastcoast",
    },
    {
        "name": "West Coast Team",
        "alias_name": "westcoast",
    },
    {
        "name": "SMB Team",
        "alias_name": "smb",
    },
    {
        "name": "Enterprise Accounts",
        "alias_name": "enterprise",
    },
    {
        "name": "Channel Partners",
        "alias_name": "channel",
    },
]

USER_ROLES_CONFIG = [
    {"role_name": "Sales Rep", "count": 10},
    {"role_name": "Pre-Sales", "count": 3},
    {
        "role_name": "Sales Manager",
        "count": 5,
    },
    {
        "role_name": "Marketing Manager",
        "count": 1,
    },
]

PRODUCT_CATEGORIES = [
    "Home Essentials",
    "Electronics",
    "Apparel",
    "Health & Beauty",
    "Office Supplies",
    "Gift Sets & Bundles",
]

SCRAP_REASONS = [
    "Damaged during shipping",
    "Defective",
    "Expired",
    "Obsolete",
    "Overstocked",
    "Returned and defective",
    "Damaged packaging",
    "Scratched lenses",
    "Defective stitching",
    "Broken",
    "Unsellable",
    "Out of season",
]

LEAD_MINING_REQUESTS_DATA = [
    {
        "name_prefix": "Tech Leads Q3",
        "leads_count": 5,
        "country_names": ["Vietnam", "United States"],
        "industry_names": ["Software & Services", "Technology Hardware & Equipment"],  # Updated
        "sales_team_name": "SMB Team",
        "salesperson_name": "Alice Johnson",
        "tag_names": ["Hot Lead", "Enterprise"],
    },
    {
        "name_prefix": "Edu Leads APAC",
        "leads_count": 8,
        "country_names": ["Singapore", "Australia"],
        "industry_names": ["Commercial & Professional Services", "Media"],  # Updated (Education not directly listed, using related)
        "sales_team_name": "East Coast Team",
        "salesperson_name": "Charlie Brown",
        "tag_names": ["New Opportunity", "Follow-up"],
    },
    {
        "name_prefix": "Manufacturing US",
        "leads_count": 3,
        "country_names": ["United States"],
        "industry_names": ["Capital Goods", "Materials"],  # Updated (Manufacturing not directly listed, using related)
        "sales_team_name": "West Coast Team",
        "salesperson_name": "Bob Jones",
        "tag_names": ["High Value"],
    },
    {
        "name_prefix": "Global Finance Leads",
        "leads_count": 10,
        "country_names": ["United Kingdom", "Germany", "Singapore"],
        "industry_names": ["Banks & Insurance", "Diversified Financials & Financial Services"],  # Updated
        "sales_team_name": "Enterprise Accounts",
        "salesperson_name": "Fiona Wilson",
        "tag_names": ["Enterprise", "Long-term"],
    },
]

BANK_NAMES = [
    "JPMorgan Chase Bank",
    "Bank of America",
    "Wells Fargo Bank",
    "Citibank",
    "U.S. Bank",
    "PNC Bank",
    "Truist Bank",
    "Goldman Sachs Bank USA",
    "Capital One Bank",
    "TD Bank, N.A.",
    "Charles Schwab Bank",
    "Bank of New York Mellon",
    "State Street Bank and Trust Company",
    "Fifth Third Bank",
    "KeyBank",
    "Citizens Bank",
    "Huntington National Bank",
    "Regions Bank",
    "M&T Bank",
    "Santander Bank, N.A.",
    "BMO Harris Bank N.A.",
    "Comerica Bank",
    "Discover Bank",
    "Synchrony Bank",
    "Ally Bank",
    "Vanguard National Bank",
    "Zions Bancorporation, N.A.",
    "Associated Bank",
    "First Horizon Bank",
    "BOKF, NA (BOK Financial)",
    "Webster Bank",
    "Bank of the West",
    "SVB (Silicon Valley Bank)",
    "Flagstar Bank",
    "Wintrust Bank",
    "Commerce Bank",
    "First Citizens Bank",
    "Ameris Bank",
    "Western Alliance Bank",
    "United Community Bank",
    "Old National Bank",
    "Arvest Bank",
    "UMB Bank, N.A.",
    "Frost Bank",
    "Banner Bank",
    "PacWest Bank",
    "East West Bank",
    "F.N.B. Corporation",
    "MidFirst Bank",
    "Home Bancorp",
    "Texas Capital Bank",
    "FirstBank (Colorado)",
    "WaFd Bank",
    "Columbia Bank",
    "Community Trust Bank",
    "OceanFirst Bank",
    "People's United Bank",
    "Mechanics Bank",
    "Tri Counties Bank",
    "First Hawaiian Bank",
    "Alaska USA Federal Credit Union",
    "Navy Federal Credit Union",
    "USAA Federal Savings Bank",
]

DEFAULT_ADDRESS_ID = 1
DEFAULT_COUNTRY_ID = 233  # United States
DEFAULT_ADMIN_USER_ID = 2
DEFAULT_EMPLOYEE_ID = 1
