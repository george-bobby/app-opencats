SYSTEM_PROMPT = """You are an expert in generating realistic contact profiles for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic contact profiles representing hiring managers, HR personnel, and recruiters.
Focus on creating realistic patterns that reflect actual corporate contact diversity."""

USER_PROMPT = """Generate {batch_size} realistic contacts for an ATS platform.

IMPORTANT REQUIREMENTS:
- First name is MANDATORY
- Last name is MANDATORY
- About {email_percentage}% should have email addresses
- About {phone_percentage}% should have phone numbers
- Use {variety_factor}% more diverse patterns for large-scale generation{excluded_emails_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "first_name": "Sarah",
    "last_name": "Johnson",
    "title": "HR Manager",
    "company_id": 1,
    "email": "sarah.johnson@techsolutions.com",
    "phone_work": "(512) 555-0150",
    "phone_cell": "(512) 555-0151",
    "phone_other": null,
    "address": "123 Business Blvd",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "notes": "Primary contact for technical positions",
    "entered_by": 1,
    "owner": 1,
    "is_hot": 1
  }},
  {{
    "first_name": "Michael",
    "last_name": "Davis",
    "title": "Recruiter",
    "company_id": 2,
    "email": null,
    "phone_work": null,
    "phone_cell": null,
    "phone_other": null,
    "address": null,
    "city": "San Francisco",
    "state": "CA",
    "zip": null,
    "notes": null,
    "entered_by": 1,
    "owner": 1,
    "is_hot": 0
  }}
]

Generate exactly {batch_size} unique contacts with maximum variety and NO repetitive patterns:"""

EXCLUDED_EMAILS_TEMPLATE = """

DO NOT USE THESE EMAILS: {emails_list}"""
