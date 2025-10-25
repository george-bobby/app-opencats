SYSTEM_PROMPT = """You are an expert in generating realistic customer data for e-commerce platforms.
Your task is to create diverse, authentic American customer profiles with varied demographics, names, and contact information.
Focus on creating realistic patterns that reflect actual e-commerce customer diversity."""

USER_PROMPT = """Generate {batch_size} realistic American customers for an e-commerce platform.

IMPORTANT REQUIREMENTS:
- Email is MANDATORY
- First name is MANDATORY
- Other fields are OPTIONAL
- About {personal_info_percentage}% should have last_name and phone
- About {company_percentage}% should have company_name
- Use {variety_factor}% more diverse patterns for large-scale generation{excluded_emails_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "email": "jennifer.martinez@gmail.com",
    "first_name": "Jennifer", 
    "last_name": "Martinez",
    "phone": "(512) 555-0147",
    "company_name": "Martinez Consulting LLC"
  }},
  {{
    "email": "alex.chen2024@yahoo.com",
    "first_name": "Alex",
    "last_name": null, 
    "phone": null,
    "company_name": null
  }}
]

Generate exactly {batch_size} unique customers with maximum variety and NO repetitive patterns:"""

EXCLUDED_EMAILS_TEMPLATE = """

DO NOT USE THESE EMAILS: {emails_list}"""
