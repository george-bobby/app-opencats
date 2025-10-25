"""
Documentation Management for GitHub Import
"""

from datetime import datetime

from common.logger import logger


class DocumentationManager:
    """Handles documentation creation"""

    def __init__(self, gitlab_client):
        self.gitlab = gitlab_client

    def create_github_data_docs(self, project_id, owner, repo, data):
        """Create GitHub repository data documentation"""
        if not data:
            logger.warning("No GitHub data provided for documentation")
            return

        stargazers = data.get("stargazers", [])
        watchers = data.get("watchers", [])
        forks = data.get("forks", [])
        # workflows = data.get("workflows", [])  # REMOVED - not used since workflows are disabled

        content = f"""# GitHub Repository Data for {owner}/{repo}

## 🌟 Stargazers ({len(stargazers)})
"""

        for star in stargazers[:50]:  # Limit to 50 for readability
            login = star.get("login", "Unknown")
            html_url = star.get("html_url", "#")
            content += f"- [@{login}]({html_url})\n"

        if len(stargazers) > 50:
            content += f"... and {len(stargazers) - 50} more\n"

        content += f"""

## 👀 Watchers ({len(watchers)})
"""

        for watcher in watchers[:50]:
            login = watcher.get("login", "Unknown")
            html_url = watcher.get("html_url", "#")
            content += f"- [@{login}]({html_url})\n"

        if len(watchers) > 50:
            content += f"... and {len(watchers) - 50} more\n"

        content += f"""

## 🍴 Forks ({len(forks)})
"""

        for fork in forks[:50]:
            name = fork.get("name", "Unknown")
            html_url = fork.get("html_url", "#")
            owner_name = fork.get("owner", "Unknown")
            stars = fork.get("stargazers_count", 0)
            content += f"- [{name}]({html_url}) by @{owner_name} ({stars} ⭐)\n"

        if len(forks) > 50:
            content += f"... and {len(forks) - 50} more\n"

        # CI/CD WORKFLOWS DOCUMENTATION COMMENTED OUT - User requested removal
        # content += f"""

        # ## ⚡ GitHub Actions ({len(workflows)})
        # """

        # for workflow in workflows:
        #     # GitHub workflows API doesn't always provide html_url, so construct it or use path
        #     workflow_url = workflow.get("html_url", f"https://github.com/{owner}/{repo}/blob/main/{workflow.get('path', '')}")
        #     content += f"- [{workflow.get('name', 'Unnamed Workflow')}]({workflow_url}) - {workflow.get('path', 'Unknown path')}\n"

        content += f"""

---
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

        success = self.gitlab.create_file(project_id, "GITHUB_DATA.md", content, "Add GitHub repository data documentation")

        if success:
            logger.succeed("GitHub data documentation created")
        else:
            logger.warning("Failed to create GitHub data documentation")

    def create_user_mapping_docs(self, project_id, github_users, mapping_analysis):
        """Create user mapping documentation"""
        if not github_users or not mapping_analysis:
            logger.warning("Missing github_users or mapping_analysis for user mapping docs")
            return

        exact_matches = mapping_analysis.get("exact_username_matches", {})
        email_matches = mapping_analysis.get("potential_email_matches", {})
        unmappable = mapping_analysis.get("unmappable_users", {})

        content = f"""# User Mapping Analysis

## Summary
- Total GitHub users: {len(github_users)}
- Exact username matches: {len(exact_matches)} ✅
- Email matches: {len(email_matches)} ⚡
- Unmappable users: {len(unmappable)} ❌

## Exact Username Matches ({len(exact_matches)})
"""

        for gh_user, gl_user in exact_matches.items():
            gl_username = gl_user.get("username", "Unknown") if isinstance(gl_user, dict) else str(gl_user)
            content += f"- **{gh_user}** → **{gl_username}**\n"

        content += f"""

## Email Matches ({len(email_matches)})
"""

        for gh_user, gl_user in email_matches.items():
            gl_username = gl_user.get("username", "Unknown") if isinstance(gl_user, dict) else str(gl_user)
            content += f"- **{gh_user}** → **{gl_username}**\n"

        content += f"""

## Unmappable Users ({len(unmappable)})
"""

        for gh_user, gh_data in unmappable.items():
            roles = ", ".join(gh_data.get("roles", [])) if isinstance(gh_data, dict) else "Unknown roles"
            content += f"- **{gh_user}** ({roles})\n"

        content += f"""

---
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

        success = self.gitlab.create_file(project_id, "USER_MAPPING_ANALYSIS.md", content, "Add user mapping analysis")

        if success:
            logger.succeed("User mapping documentation created")
        else:
            logger.warning("Failed to create user mapping documentation")

    def create_user_credentials_file(self, project_id, auto_create_result):
        """Create user credentials file"""
        if not auto_create_result:
            logger.warning("No auto_create_result provided for user credentials")
            return

        user_credentials = auto_create_result.get("user_credentials", [])
        failed_users = auto_create_result.get("failed_users", [])

        content = f"""# 🔐 AUTO-CREATED GITLAB USERS

## Successfully Created Users ({len(user_credentials)})

"""

        for cred in user_credentials:
            name = cred.get("name", "Unknown")
            github_username = cred.get("github_username", "Unknown")
            gitlab_username = cred.get("gitlab_username", "Unknown")
            email = cred.get("email", "Unknown")
            password = cred.get("password", "Unknown")

            content += f"""### {name} (@{github_username})
- **GitLab Username:** `{gitlab_username}`
- **Email:** `{email}`
- **Temporary Password:** `{password}`
- **Action:** User must reset password on first login

---

"""

        if failed_users:
            content += f"""## Failed Creations ({len(failed_users)})

"""
            for failed in failed_users:
                github_username = failed.get("github_username", "Unknown")
                error = failed.get("error", "Unknown error")
                content += f"- **{github_username}**: {error}\n"

        content += f"""

---
*Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*🔒 This file contains sensitive information - handle securely!*
"""

        success = self.gitlab.create_file(project_id, "USER_CREDENTIALS_SECURE.md", content, "Add auto-created user credentials (SECURE)")

        if success:
            logger.succeed("User credentials file created")
        else:
            logger.warning("Failed to create user credentials file")

    # CI/CD PRESERVE GITHUB ACTIONS METHOD COMMENTED OUT - User requested removal
    # def preserve_github_actions(self, _project_id, _owner, _repo, _workflows):
    #     """Preserve GitHub Actions workflows"""
    #     if not workflows:
    #         logger.info("No GitHub Actions workflows to preserve")
    #         return
    #
    #     for workflow in workflows:
    #         if not isinstance(workflow, dict):
    #             logger.warning(f"Invalid workflow data: {workflow}")
    #             continue
    #
    #         workflow_name = workflow.get("name", "Unnamed Workflow")
    #         workflow_path = workflow.get("path", "Unknown path")
    #         # Create a simple conversion to GitLab CI
    #         gitlab_ci_content = f"""# Converted from GitHub Actions: {workflow_name}
    # # Original workflow: {workflow_path}

    # stages:
    #   - build
    #   - test
    #   - deploy

    # build:
    #   stage: build
    #   script:
    #     - echo "This workflow was converted from GitHub Actions"
    #     - echo "Original workflow: {workflow_name}"
    #     - echo "Please review and update this CI configuration"

    # # Original GitHub Actions workflow was located at: {workflow_path}
    # # Please review the original workflow and update this CI configuration accordingly
    # """

    #         # Create GitLab CI file
    #         safe_name = workflow_name.lower().replace(" ", "-").replace("/", "-")
    #         ci_filename = f"gitlab-ci-{safe_name}.yml"
    #         success = self.gitlab.create_file(project_id, ci_filename, gitlab_ci_content, f"Convert GitHub Actions: {workflow_name}")

    #         if success:
    #             logger.success(f"GitHub Actions workflow converted: {workflow_name}")
    #         else:
    #             logger.warning(f"Failed to convert workflow: {workflow_name}")

    #     logger.info(f"GitHub Actions preservation completed for {len(workflows)} workflows")

    def preserve_github_actions(self, _project_id, _owner, _repo, _workflows):
        """Preserve GitHub Actions workflows - DISABLED BY USER REQUEST"""
        logger.info("GitHub Actions preservation skipped - disabled by user request")
        return
