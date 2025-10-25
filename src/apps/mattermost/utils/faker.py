import random

from faker import Faker
from faker.providers import BaseProvider


# Job positions relevant to a US-based SME tech company
TECH_POSITIONS = [
    "Software Engineer",
    "Senior Software Engineer",
    "Frontend Developer",
    "Backend Developer",
    "Full Stack Developer",
    "DevOps Engineer",
    "System Administrator",
    "Database Administrator",
    "QA Engineer",
    "QA Analyst",
    "Technical Lead",
    "Engineering Manager",
    "Product Manager",
    "Product Owner",
    "UX Designer",
    "UI Designer",
    "UX/UI Designer",
    "Data Analyst",
    "Business Analyst",
    "Project Manager",
    "Scrum Master",
    "Marketing Manager",
    "Digital Marketing Specialist",
    "Content Marketing Specialist",
    "Social Media Manager",
    "Sales Manager",
    "Account Manager",
    "Customer Success Manager",
    "Sales Representative",
    "HR Manager",
    "HR Coordinator",
    "Recruiter",
    "Office Manager",
    "Operations Manager",
    "Finance Manager",
    "Accountant",
    "Controller",
    "CEO",
    "CTO",
    "VP of Engineering",
    "VP of Sales",
    "VP of Marketing",
    "Customer Support Specialist",
    "Technical Support Engineer",
    "Security Engineer",
    "Solutions Architect",
    "Cloud Engineer",
]


class MattermostUserProvider(BaseProvider):
    def __init__(self: Faker, generator, seen_usernames: set[str] | None = None, seen_emails: set[str] | None = None):
        super().__init__(generator)
        self.seen_usernames = seen_usernames or set()
        self.seen_emails = seen_emails or set()

    def unique_username_email(self, max_attempts: int = 100):
        """Generate a unique username and email pair."""
        for _ in range(max_attempts):
            first_name = self.generator.first_name().lower()
            last_name = self.generator.last_name().lower()

            # Clean names to ensure they work as usernames
            first_name = "".join(c for c in first_name if c.isalnum())
            last_name = "".join(c for c in last_name if c.isalnum())

            username = f"{first_name}.{last_name}"
            email = f"{username}@vertexon.com"

            if username not in self.seen_usernames and email not in self.seen_emails:
                self.seen_usernames.add(username)
                self.seen_emails.add(email)
                return username, email, first_name.title(), last_name.title()

        # If we can't find a unique combination, add a number
        base_first = self.generator.first_name().lower()
        base_last = self.generator.last_name().lower()
        base_first = "".join(c for c in base_first if c.isalnum())
        base_last = "".join(c for c in base_last if c.isalnum())

        for i in range(1, 1000):
            username = f"{base_first}.{base_last}{i}"
            email = f"{username}@vertexon.com"

            if username not in self.seen_usernames and email not in self.seen_emails:
                self.seen_usernames.add(username)
                self.seen_emails.add(email)
                return username, email, base_first.title(), base_last.title()

        raise ValueError("Unable to generate unique username/email after many attempts")

    def mattermost_user(self, seen_usernames: set[str] | None = None, seen_emails: set[str] | None = None):
        """Generate a complete Mattermost user profile with unique username and email."""
        if seen_usernames:
            self.seen_usernames.update(seen_usernames)
        if seen_emails:
            self.seen_emails.update(seen_emails)

        username, email, first_name, last_name = self.unique_username_email()
        faker_instance = Faker()
        gender = faker_instance.random_element(elements=["male", "female"])
        first_name = faker_instance.first_name_female() if gender == "female" else faker_instance.first_name_male()

        return {
            "email": email,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "nickname": first_name,
            "position": random.choice(TECH_POSITIONS),
            "roles": "system_user",
            "gender": gender,
        }


def create_faker_with_user_tracking(seen_usernames: set[str] | None = None, seen_emails: set[str] | None = None):
    """Create a faker instance with user tracking for global uniqueness."""
    faker = Faker()
    provider = MattermostUserProvider(faker, seen_usernames, seen_emails)
    faker.add_provider(provider)
    return faker


# Default faker instance
faker = Faker()
provider = MattermostUserProvider(faker)
faker.add_provider(provider)
