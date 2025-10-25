import re

from faker import Faker
from faker.providers import BaseProvider


class CustomPhoneProvider(BaseProvider):
    def custom_phone_number(self):
        area_code = self.random_int(min=100, max=999)
        prefix = self.random_int(min=100, max=999)
        line_number = self.random_int(min=1000, max=9999)
        return f"({area_code}) {prefix}-{line_number}"


class CustomCompanyProvider(BaseProvider):
    def company_with_email(self):
        # Randomly decide between company or person (50-50 chance)
        is_company = self.random_element([True, False])

        if is_company:
            name = self.generator.company()
            # Convert company name to lowercase, remove special chars (including hyphens), and remove spaces
            email_prefix = re.sub(r"[^\w\s]", "", name.lower()).replace(" ", "")
        else:
            first_name = self.generator.first_name()
            last_name = self.generator.last_name()
            name = f"{first_name} {last_name}"
            # Use lowercase for email
            first_name = first_name.lower()
            last_name = last_name.lower()
            email_prefix = re.sub(r"[^\w\s-]", "", name.lower()).replace(" ", "")

        first_initial = first_name[0] if not is_company else None
        last_initial = last_name[0] if not is_company else None

        # Common business email domains
        domains = ["com", "org", "io", "co"]
        domain = self.random_element(domains)

        if is_company:
            # Company email patterns
            patterns = [
                lambda c: f"info@{c}.{domain}",
                lambda c: f"contact@{c}.{domain}",
                lambda c: f"sales@{c}.{domain}",
                lambda c: f"hello@{c}.{domain}",
                lambda c: f"office@{c}.{domain}",
            ]
        else:
            # Personal email patterns
            patterns = [
                lambda c: f"{first_name}@{c}.{domain}",
                lambda c: f"{first_name}.{last_name}@{c}.{domain}",
                lambda c: f"{first_initial}{last_name}@{c}.{domain}",
                lambda c: f"{first_name}{last_initial}@{c}.{domain}",
                lambda c: f"{first_initial}.{last_name}@{c}.{domain}",
                lambda c: f"{last_name}.{first_name}@{c}.{domain}",
                lambda c: f"{first_initial}{last_initial}@{c}.{domain}",
            ]

        email = self.random_element(patterns)(email_prefix)

        # Extract domain from email and create website
        email_parts = email.split("@")
        if len(email_parts) > 1:
            website_domain = email_parts[1]
        else:
            # Take only the last part of the email prefix for the domain
            simplified_domain = email_prefix.split(".")[-1]
            website_domain = f"{simplified_domain}.{domain}"

        website = f"https://www.{website_domain}"

        return {"name": name, "email": email, "website": website}


faker = Faker()
faker.add_provider(CustomPhoneProvider)
faker.add_provider(CustomCompanyProvider)
