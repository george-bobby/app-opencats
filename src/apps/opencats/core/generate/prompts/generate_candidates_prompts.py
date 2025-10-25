SYSTEM_PROMPT = """You are an expert in generating realistic candidate profiles for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic candidate profiles with varied skills, experience levels, and backgrounds.
Focus on creating realistic patterns that reflect actual job market diversity."""

USER_PROMPT = """Generate {batch_size} realistic candidates for an ATS platform.

IMPORTANT REQUIREMENTS:
- First name is MANDATORY
- Last name is MANDATORY
- Email is MANDATORY
- Phone is MANDATORY
- About {experience_percentage}% should have work experience
- About {education_percentage}% should have education details
- Use {variety_factor}% more diverse patterns for large-scale generation{excluded_emails_text}{excluded_names_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "first_name": "Jennifer",
    "last_name": "Martinez",
    "email": "jennifer.martinez@gmail.com",
    "phone": "(512) 555-0147",
    "address": "123 Main St, Austin, TX 78701",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "source": "Website",
    "key_skills": "Python, JavaScript, React",
    "current_employer": "Tech Solutions Inc",
    "can_relocate": 1,
    "notes": "Experienced software developer with strong problem-solving skills"
  }},
  {{
    "first_name": "Alex",
    "last_name": "Chen",
    "email": "alex.chen2024@yahoo.com",
    "phone": "(415) 555-0198",
    "address": null,
    "city": "San Francisco",
    "state": "CA", 
    "zip": null,
    "source": "Referral",
    "key_skills": null,
    "current_employer": null,
    "can_relocate": 0,
    "notes": null
  }}
]

Generate exactly {batch_size} unique candidates with maximum variety and NO repetitive patterns:"""

EXCLUDED_EMAILS_TEMPLATE = """

DO NOT USE THESE EMAILS: {emails_list}"""

EXCLUDED_NAMES_TEMPLATE = """

DO NOT USE THESE NAMES: {names_list}"""
