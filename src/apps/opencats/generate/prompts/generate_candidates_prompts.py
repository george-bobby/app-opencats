SYSTEM_PROMPT = """You are an expert in generating realistic candidate profiles for an Applicant Tracking System (ATS).
Your task is to create diverse, authentic candidate profiles with varied skills, experience levels, and backgrounds.
Focus on creating realistic patterns that reflect actual job market diversity."""

USER_PROMPT = """Generate {batch_size} realistic candidates for an ATS platform.

IMPORTANT REQUIREMENTS:
- firstName is MANDATORY
- lastName is MANDATORY
- email1 is MANDATORY
- phoneHome, phoneCell, or phoneWork is MANDATORY (at least one phone number)
- About {experience_percentage}% should have work experience
- About {education_percentage}% should have education details
- Use {variety_factor}% more diverse patterns for large-scale generation

CONTACT INFORMATION (MUST POPULATE):
- phoneCell: Cell phone number (85% chance - IMPORTANT: populate frequently)
- phoneWork: Work phone number (70% chance - IMPORTANT: populate frequently)
- webSite: Personal/professional website (50% chance)
- bestTimeToCall: Best time to contact (80% chance - examples: "9 AM - 5 PM", "After 6 PM", "Weekends preferred")

EMPLOYMENT DETAILS (MUST POPULATE):
- isHot: 1 for high-priority candidates (25% chance), 0 otherwise
- canRelocate: 1 if willing to relocate (60% chance), 0 otherwise
- dateAvailable: Date available for work in MM-DD-YY format (80% chance)
- currentEmployer: Current company name (70% chance for employed candidates)
- currentPay: Current annual salary as number (60% chance for employed - examples: "75000", "120000")
- desiredPay: Desired annual salary as number (90% chance - examples: "85000", "140000")

SKILLS & EXPERIENCE GUIDANCE:
- Use relevant skills from: {relevant_skills}
- Align experience with job titles like: {relevant_titles}
- Make keySkills realistic for the candidate's experience level
- Consider current market demand for skills when assigning
- IMPORTANT: Candidates will be matched to job orders, so ensure skills align with common tech positions
- Mix of junior, mid-level, and senior candidates to match various job levels{excluded_emails_text}{excluded_names_text}

Return ONLY a JSON array with this exact structure:
[
  {{
    "firstName": "Jennifer",
    "lastName": "Martinez",
    "email1": "jennifer.martinez@gmail.com",
    "phoneHome": "(512) 555-0147",
    "phoneCell": "(512) 555-0148",
    "phoneWork": "(512) 555-0149",
    "address": "123 Main St, Austin, TX 78701",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "source": "Website",
    "keySkills": "Python, JavaScript, React, AWS",
    "dateAvailable": "12-01-24",
    "currentEmployer": "Tech Solutions Inc",
    "canRelocate": 1,
    "currentPay": "95000",
    "desiredPay": "110000",
    "notes": "Experienced software developer with strong problem-solving skills",
    "webSite": "https://jennifer-martinez.dev",
    "bestTimeToCall": "9 AM - 5 PM",
    "isHot": 1
  }},
  {{
    "firstName": "Alex",
    "lastName": "Chen",
    "email1": "alex.chen2024@yahoo.com",
    "phoneCell": "(415) 555-0198",
    "phoneWork": null,
    "address": null,
    "city": "San Francisco",
    "state": "CA", 
    "zip": null,
    "source": "Referral",
    "keySkills": "Java, Spring, MySQL, DevOps",
    "dateAvailable": "01-15-25",
    "currentEmployer": null,
    "canRelocate": 0,
    "currentPay": null,
    "desiredPay": "120000",
    "notes": null,
    "webSite": null,
    "bestTimeToCall": "After 6 PM",
    "isHot": 0
  }}
]

Generate exactly {batch_size} unique candidates with maximum variety and NO repetitive patterns:"""

EXCLUDED_EMAILS_TEMPLATE = """

DO NOT USE THESE EMAILS: {emails_list}"""

EXCLUDED_NAMES_TEMPLATE = """

DO NOT USE THESE NAMES: {names_list}"""
