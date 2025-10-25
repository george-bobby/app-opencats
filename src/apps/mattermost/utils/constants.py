"""
Constants for Mattermost JSON file paths.
"""

from pathlib import Path


# Base data directory
DATA_DIR = Path(__file__).parent.parent / "data"

# Main JSON files
TEAMS_JSON = DATA_DIR / "teams.json"
USERS_JSON = DATA_DIR / "users.json"
CONFIG_JSON = DATA_DIR / "config.json"

# Channel messages directory
CHANNEL_MESSAGES_DIR = DATA_DIR / "channel-messages"

# All JSON files list for easy iteration
ALL_JSON_FILES = [
    TEAMS_JSON,
    USERS_JSON,
    CONFIG_JSON,
]

# All channel message files (dynamically discovered)
ALL_CHANNEL_MESSAGE_FILES = list(CHANNEL_MESSAGES_DIR.glob("*.json"))

# User generation constants
BATCH_SIZE = 50

# DM generation constants
THREAD_ATTACHMENT_PROBABILITY = 10

# Reaction probabilities (in percentage)
CHANNEL_MESSAGE_REACTION_PROBABILITY = 40  # Percentage chance for channel messages to have reactions
DM_MESSAGE_REACTION_PROBABILITY = 30  # Percentage chance for DM messages to have reactions

# Reaction participation rates (as decimal percentages)
# For DM messages (small groups)
DM_REACTION_MIN_PARTICIPATION = 0.10  # 10% minimum participation
DM_REACTION_MAX_PARTICIPATION = 0.30  # 30% maximum participation

# For channel messages (larger groups)
CHANNEL_REACTION_HIGH_MIN_PARTICIPATION = 0.15  # 15% for messages marked as needing reactions
CHANNEL_REACTION_HIGH_MAX_PARTICIPATION = 0.40  # 40% for messages marked as needing reactions
CHANNEL_REACTION_LOW_MIN_PARTICIPATION = 0.05  # 5% for regular messages
CHANNEL_REACTION_LOW_MAX_PARTICIPATION = 0.15  # 15% for regular messages

# Define positions that should be unique (only one per company)
UNIQUE_POSITIONS = {
    "Chief Executive Officer",
    "CEO",
    "Chief Technology Officer",
    "CTO",
    "Chief Financial Officer",
    "CFO",
    "Chief Operating Officer",
    "COO",
    "Chief Marketing Officer",
    "CMO",
    "Chief Human Resources Officer",
    "CHRO",
    "Chief Product Officer",
    "CPO",
    "Chief Data Officer",
    "CDO",
    "Chief Security Officer",
    "CSO",
    "VP of Engineering",
    "Vice President of Engineering",
    "VP of Product",
    "Vice President of Product",
    "VP of Marketing",
    "Vice President of Marketing",
    "VP of Operations",
    "Vice President of Operations",
    "VP of Sales",
    "Vice President of Sales",
    "VP of Human Resources",
    "Vice President of Human Resources",
    "Head of Engineering",
    "Engineering Director",
    "Head of Product",
    "Product Director",
    "Head of Marketing",
    "Marketing Director",
    "Head of Operations",
    "Operations Director",
    "Head of Sales",
    "Sales Director",
    "Head of Human Resources",
    "HR Director",
    "Head of Security",
    "Security Director",
    "Head of Data",
    "Data Director",
    "HR Manager",
    "Human Resources Manager",
    "Finance Manager",
    "Financial Manager",
    "Operations Manager",
    "General Manager",
}
