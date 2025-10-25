SYSTEM_PROMPT = """You are an expert in generating realistic company profiles for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic company profiles with varied industries, sizes, and locations.
Focus on creating realistic patterns that reflect actual business diversity."""

USER_PROMPT = """Generate {batch_size} realistic companies for an ATS platform.

IMPORTANT REQUIREMENTS:
- Company name is MANDATORY
- About {contact_percentage}% should have contact information
- About {address_percentage}% should have complete address details
- Use {variety_factor}% more diverse patterns for large-scale generation{excluded_names_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "name": "Tech Solutions Inc",
    "address": "123 Business Blvd",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "phone": "(512) 555-0100",
    "fax": "(512) 555-0101",
    "url": "https://techsolutions.com",
    "key_technologies": "Python, React, AWS",
    "notes": "Leading software development company specializing in web applications",
    "entered_by": 1,
    "owner": 1,
    "is_hot": 1
  }},
  {{
    "name": "Marketing Dynamics LLC",
    "address": null,
    "city": "San Francisco",
    "state": "CA",
    "zip": null,
    "phone": null,
    "fax": null,
    "url": null,
    "key_technologies": null,
    "notes": null,
    "entered_by": 1,
    "owner": 1,
    "is_hot": 0
  }}
]

Generate exactly {batch_size} unique companies with maximum variety and NO repetitive patterns:"""

EXCLUDED_NAMES_TEMPLATE = """

DO NOT USE THESE COMPANY NAMES: {names_list}"""
