"""
User Management for GitHub to GitLab mapping
"""

import secrets
import string
import time

from common.logger import logger


class UserManager:
    """Handles user analysis and creation"""

    def __init__(self, github_client, gitlab_client):
        self.github = github_client
        self.gitlab = gitlab_client

    def analyze_mapping(self, github_users, gitlab_users):
        """Analyze user mapping potential"""
        # Convert GitLab users to lookup dictionaries
        gitlab_by_username = {u["username"].lower(): u for u in gitlab_users.values()}
        gitlab_by_email = {u["email"].lower(): u for u in gitlab_users.values() if u["email"]}

        mapping_analysis = {"exact_username_matches": {}, "potential_email_matches": {}, "unmappable_users": {}}

        for gh_username, gh_user in github_users.items():
            gh_username_lower = gh_username.lower()
            gh_email_lower = gh_user.get("email", "").lower() if gh_user.get("email") else ""

            mapped = False

            # Check exact username match
            if gh_username_lower in gitlab_by_username:
                mapping_analysis["exact_username_matches"][gh_username] = gitlab_by_username[gh_username_lower]
                mapped = True

            # Check email match
            elif gh_email_lower and gh_email_lower in gitlab_by_email:
                mapping_analysis["potential_email_matches"][gh_username] = gitlab_by_email[gh_email_lower]
                mapped = True

            # If no mapping found
            if not mapped:
                mapping_analysis["unmappable_users"][gh_username] = gh_user

        total = len(github_users)
        mappable = len(mapping_analysis["exact_username_matches"]) + len(mapping_analysis["potential_email_matches"])
        unmappable = len(mapping_analysis["unmappable_users"])

        logger.info(f"Mapping analysis: {mappable}/{total} mappable, {unmappable} need creation")

        return mapping_analysis

    def auto_create_users(self, unmappable_users):
        """Auto-create GitLab users for unmappable GitHub users"""
        created_users = []
        failed_users = []
        user_credentials = []

        for gh_username, gh_user_data in unmappable_users.items():
            result = self._create_gitlab_user(gh_user_data)

            if result["success"]:
                created_users.append(result)
                user_credentials.append(
                    {
                        "github_username": gh_username,
                        "gitlab_username": result["user"]["username"],
                        "email": result["user"]["email"],
                        "password": result.get("password", ""),
                        "name": result["user"]["name"],
                    }
                )
            else:
                failed_users.append({"github_username": gh_username, "error": result["error"]})

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        logger.info(f"User creation: {len(created_users)} created, {len(failed_users)} failed")

        return {"created_users": created_users, "failed_users": failed_users, "user_credentials": user_credentials}

    def _create_gitlab_user(self, github_user_data):
        """Create a GitLab user from GitHub user data"""
        gh_username = github_user_data["login"]
        gh_email = github_user_data.get("email", "")
        gh_name = github_user_data.get("name", "") or gh_username

        # Handle missing email
        if not gh_email:
            gh_email = f"{gh_username}@github-import.placeholder"

        # Check if username is available
        original_username = gh_username
        attempt = 0
        while True:
            response = self.gitlab._request("GET", f"/users?username={gh_username}")
            if response and response.status_code == 200:
                users = response.json()
                if not users:  # Username available
                    break
                else:
                    attempt += 1
                    gh_username = f"{original_username}_{attempt}"
            else:
                break

        # Create user data
        password = self._generate_password()
        user_data = {
            "username": gh_username,
            "name": gh_name,
            "email": gh_email,
            "password": password,
            "skip_confirmation": True,
            "reset_password": True,
            "can_create_group": True,
            "projects_limit": 10,
        }

        result = self.gitlab.create_user(user_data)
        if result["success"]:
            result["password"] = password

        return result

    def _generate_password(self, length=12):
        """Generate secure password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))
