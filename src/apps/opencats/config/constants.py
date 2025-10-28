"""OpenCATS application constants and enums."""

from enum import Enum

from apps.opencats.config.settings import settings


class OpenCATSEndpoint(Enum):
    """OpenCATS form submission endpoints."""

    LOGIN = "/index.php?m=login&a=attemptLogin"
    COMPANIES_ADD = "/index.php?m=companies&a=add"
    CONTACTS_ADD = "/index.php?m=contacts&a=add"
    CANDIDATES_ADD = "/index.php?m=candidates&a=add"
    JOBORDERS_ADD = "/index.php?m=joborders&a=add"
    CALENDAR_ADD = "/index.php?m=calendar&a=addEvent"
    AJAX = "/ajax.php"


class OpenCATSDataItemType(Enum):
    """Data item types for lists."""

    CANDIDATE = 100
    COMPANY = 200
    CONTACT = 300
    JOB_ORDER = 400


class OpenCATSEventType(Enum):
    """Calendar event types."""

    CALL = 100
    EMAIL = 200
    MEETING = 300
    INTERVIEW = 400
    PERSONAL = 500
    OTHER = 600


class OpenCATSJobType(Enum):
    """Job order types."""

    CONTRACT = "C"
    CONTRACT_TO_HIRE = "C2H"
    FREELANCE = "FL"
    HIRE = "H"


class OpenCATSEEOEthnicType(Enum):
    """EEO ethnic types."""

    AMERICAN_INDIAN = 1
    ASIAN_PACIFIC_ISLANDER = 2
    HISPANIC_LATINO = 3
    NON_HISPANIC_BLACK = 4
    NON_HISPANIC_WHITE = 5


class OpenCATSEEOVeteranType(Enum):
    """EEO veteran types."""

    NO_VETERAN_STATUS = 1
    ELIGIBLE_VETERAN = 2
    DISABLED_VETERAN = 3
    ELIGIBLE_AND_DISABLED = 4


class OpenCATSCandidateJobOrderStatus(Enum):
    """Candidate-Job Order relationship statuses."""

    NO_CONTACT = 100
    CONTACTED = 200
    SUBMITTED = 300
    APPLIED = 400
    INTERVIEWING = 500
    OFFER_EXTENDED = 600
    OFFER_ACCEPTED = 700
    OFFER_DECLINED = 800
    PLACED = 900
    REJECTED = 1000


# Random seed for consistent data generation
RANDOM_SEED = 42

# File names for generated data
COMPANIES_FILENAME = "companies.json"
CONTACTS_FILENAME = "contacts.json"
CANDIDATES_FILENAME = "candidates.json"
JOBORDERS_FILENAME = "joborders.json"
EVENTS_FILENAME = "events.json"
LISTS_FILENAME = "lists.json"

# File paths for generated data
COMPANIES_FILEPATH = settings.DATA_PATH / COMPANIES_FILENAME
CONTACTS_FILEPATH = settings.DATA_PATH / CONTACTS_FILENAME
CANDIDATES_FILEPATH = settings.DATA_PATH / CANDIDATES_FILENAME
JOBORDERS_FILEPATH = settings.DATA_PATH / JOBORDERS_FILENAME
EVENTS_FILEPATH = settings.DATA_PATH / EVENTS_FILENAME
LISTS_FILEPATH = settings.DATA_PATH / LISTS_FILENAME

# Default counts for data generation
DEFAULT_COMPANIES_COUNT = 5
DEFAULT_CONTACTS_COUNT = 15
DEFAULT_CANDIDATES_COUNT = 20
DEFAULT_JOBORDERS_COUNT = 8
DEFAULT_EVENTS_COUNT = 10
DEFAULT_LISTS_COUNT = 1

# Batch sizes for data generation
COMPANIES_BATCH_SIZE = 10
CONTACTS_BATCH_SIZE = 10
CANDIDATES_BATCH_SIZE = 12
JOBORDERS_BATCH_SIZE = 10
EVENTS_BATCH_SIZE = 15
LISTS_BATCH_SIZE = 5

# US states and cities for address generation
US_STATES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]

MAJOR_CITIES = [
    "New York",
    "Los Angeles",
    "Chicago",
    "Houston",
    "Phoenix",
    "Philadelphia",
    "San Antonio",
    "San Diego",
    "Dallas",
    "San Jose",
    "Austin",
    "Jacksonville",
    "Fort Worth",
    "Columbus",
    "Charlotte",
    "San Francisco",
    "Indianapolis",
    "Seattle",
    "Denver",
    "Washington",
    "Boston",
    "El Paso",
    "Nashville",
    "Detroit",
    "Oklahoma City",
    "Portland",
    "Las Vegas",
    "Memphis",
    "Louisville",
    "Baltimore",
    "Milwaukee",
    "Albuquerque",
    "Tucson",
    "Fresno",
    "Sacramento",
    "Kansas City",
    "Long Beach",
    "Mesa",
    "Atlanta",
    "Colorado Springs",
    "Virginia Beach",
    "Raleigh",
    "Omaha",
    "Miami",
    "Oakland",
    "Minneapolis",
    "Tulsa",
    "Wichita",
    "New Orleans",
    "Arlington",
]

# Technology skills for candidates
TECH_SKILLS = [
    "Python",
    "Java",
    "JavaScript",
    "C#",
    "C++",
    "PHP",
    "Ruby",
    "Go",
    "Rust",
    "Swift",
    "React",
    "Angular",
    "Vue.js",
    "Node.js",
    "Django",
    "Flask",
    "Spring",
    "Laravel",
    "MySQL",
    "PostgreSQL",
    "MongoDB",
    "Redis",
    "Elasticsearch",
    "Oracle",
    "AWS",
    "Azure",
    "Google Cloud",
    "Docker",
    "Kubernetes",
    "Jenkins",
    "Git",
    "Linux",
    "Windows Server",
    "MacOS",
    "Agile",
    "Scrum",
    "DevOps",
    "CI/CD",
    "Machine Learning",
    "AI",
    "Data Science",
    "Big Data",
    "Hadoop",
    "Spark",
    "Tableau",
    "Power BI",
    "Salesforce",
    "SAP",
    "Oracle ERP",
    "Jira",
    "Confluence",
]

# Company industries and technologies
COMPANY_INDUSTRIES = [
    "Technology",
    "Healthcare",
    "Finance",
    "Manufacturing",
    "Retail",
    "Education",
    "Government",
    "Non-profit",
    "Consulting",
    "Media",
    "Transportation",
    "Energy",
    "Real Estate",
    "Insurance",
    "Telecommunications",
    "Automotive",
    "Aerospace",
    "Biotechnology",
    "Pharmaceuticals",
    "Food & Beverage",
    "Hospitality",
    "Legal",
]

COMPANY_TECHNOLOGIES = [
    "Cloud Computing",
    "Artificial Intelligence",
    "Machine Learning",
    "Blockchain",
    "IoT",
    "Cybersecurity",
    "Data Analytics",
    "Mobile Development",
    "Web Development",
    "Enterprise Software",
    "SaaS",
    "E-commerce",
    "Digital Marketing",
    "CRM",
    "ERP",
    "Business Intelligence",
    "Automation",
    "Robotics",
    "AR/VR",
    "5G",
]

# Job titles and departments
JOB_TITLES = [
    "Software Engineer",
    "Senior Software Engineer",
    "Lead Software Engineer",
    "Software Architect",
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "DevOps Engineer",
    "Site Reliability Engineer",
    "Data Engineer",
    "Data Scientist",
    "Machine Learning Engineer",
    "Product Manager",
    "Project Manager",
    "Scrum Master",
    "Business Analyst",
    "Systems Analyst",
    "Database Administrator",
    "Network Administrator",
    "Security Engineer",
    "QA Engineer",
    "Test Automation Engineer",
    "UX Designer",
    "UI Designer",
    "Technical Writer",
    "Solutions Architect",
    "Cloud Engineer",
]

DEPARTMENTS = [
    "Engineering",
    "Product",
    "Design",
    "Data",
    "DevOps",
    "QA",
    "Security",
    "IT",
    "Operations",
    "Marketing",
    "Sales",
    "HR",
    "Finance",
    "Legal",
    "Customer Success",
    "Support",
    "Research",
    "Strategy",
    "Business Development",
]

# Event types and descriptions
EVENT_DESCRIPTIONS = {
    OpenCATSEventType.CALL: ["Initial screening call", "Technical phone interview", "Follow-up call", "Reference check call", "Salary negotiation call", "Client check-in call"],
    OpenCATSEventType.EMAIL: ["Send job description", "Follow-up email", "Interview confirmation", "Offer letter sent", "Rejection notification", "Status update"],
    OpenCATSEventType.MEETING: ["Team meeting", "Client kickoff", "Project review", "Strategy session", "Requirements gathering", "Stakeholder meeting"],
    OpenCATSEventType.INTERVIEW: ["Technical interview", "Behavioral interview", "Panel interview", "Final interview", "Culture fit interview", "Executive interview"],
    OpenCATSEventType.PERSONAL: ["Personal time off", "Training session", "Conference attendance", "Team building", "Professional development", "Networking event"],
    OpenCATSEventType.OTHER: ["Document review", "System maintenance", "Data backup", "Process improvement", "Vendor meeting", "Compliance check"],
}

# List names for saved lists
LIST_NAMES = [
    "Hot Candidates",
    "Top Performers",
    "Recent Graduates",
    "Senior Developers",
    "Remote Workers",
    "Local Talent",
    "Contract Candidates",
    "Full-time Candidates",
    "Priority Companies",
    "Tech Startups",
    "Enterprise Clients",
    "New Contacts",
    "Active Job Orders",
    "Urgent Positions",
    "High-paying Jobs",
    "Entry Level Jobs",
]
