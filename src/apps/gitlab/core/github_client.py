"""
GitHub API Client
"""

import requests

from apps.gitlab.config.settings import settings
from common.logger import logger


class GitHubClient:
    """GitHub API client"""

    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.base_url = "https://api.github.com"

    def _request(self, endpoint):
        """Make GitHub API request"""
        headers = {"Authorization": f"token {self.token}"}
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            return response
        except Exception as e:
            logger.fail(f"GitHub API error: {e}")
            return None

    def validate_access(self, owner, repo):
        """Validate access to repository"""
        response = self._request(f"/repos/{owner}/{repo}")
        return response and response.status_code == 200

    def get_repository(self, owner, repo):
        """Get repository information"""
        response = self._request(f"/repos/{owner}/{repo}")
        if response and response.status_code == 200:
            return response.json()
        return None

    def get_all_users(self, owner, repo):
        """Get all users involved in repository"""
        all_users = {}

        # Get collaborators
        self._get_paginated_users(f"/repos/{owner}/{repo}/collaborators", all_users, "collaborator")

        # Get issue authors
        self._get_issue_users(owner, repo, all_users)

        # Get PR users
        self._get_pr_users(owner, repo, all_users)

        return all_users

    def _get_paginated_users(self, endpoint, all_users, role):
        """Get users from paginated endpoint"""
        page = 1
        while page <= 5:  # Limit to 5 pages
            response = self._request(f"{endpoint}?page={page}&per_page=100")
            if not response or response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            for user in data:
                username = user.get("login", "")
                if username:
                    all_users[username] = {
                        "login": username,
                        "id": user.get("id", ""),
                        "email": user.get("email", ""),
                        "name": user.get("name", ""),
                        "avatar_url": user.get("avatar_url", ""),
                        "html_url": user.get("html_url", ""),
                        "roles": [role],
                    }

            page += 1
            if len(data) < 100:
                break

    def _get_issue_users(self, owner, repo, all_users):
        """Get users from issues"""
        page = 1
        while page <= 3:  # Limit pages
            response = self._request(f"/repos/{owner}/{repo}/issues?state=all&page={page}&per_page=100")
            if not response or response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            for issue in data:
                if issue.get("user"):
                    user = issue["user"]
                    username = user.get("login", "")
                    if username:
                        if username not in all_users:
                            all_users[username] = {
                                "login": username,
                                "id": user.get("id", ""),
                                "email": "",
                                "name": "",
                                "avatar_url": user.get("avatar_url", ""),
                                "html_url": user.get("html_url", ""),
                                "roles": [],
                            }
                        if "issue_author" not in all_users[username]["roles"]:
                            all_users[username]["roles"].append("issue_author")

            page += 1
            if len(data) < 100:
                break

    def _get_pr_users(self, owner, repo, all_users):
        """Get users from pull requests"""
        page = 1
        while page <= 3:  # Limit pages
            response = self._request(f"/repos/{owner}/{repo}/pulls?state=all&page={page}&per_page=100")
            if not response or response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            for pr in data:
                if pr.get("user"):
                    user = pr["user"]
                    username = user.get("login", "")
                    if username:
                        if username not in all_users:
                            all_users[username] = {
                                "login": username,
                                "id": user.get("id", ""),
                                "email": "",
                                "name": "",
                                "avatar_url": user.get("avatar_url", ""),
                                "html_url": user.get("html_url", ""),
                                "roles": [],
                            }
                        if "pr_author" not in all_users[username]["roles"]:
                            all_users[username]["roles"].append("pr_author")

            page += 1
            if len(data) < 100:
                break

    def get_stargazers(self, owner, repo):
        """Get repository stargazers"""
        return self._get_simple_users(f"/repos/{owner}/{repo}/stargazers")

    def get_watchers(self, owner, repo):
        """Get repository watchers"""
        return self._get_simple_users(f"/repos/{owner}/{repo}/subscribers")

    def get_forks(self, owner, repo):
        """Get repository forks"""
        forks = []
        response = self._request(f"/repos/{owner}/{repo}/forks?per_page=50")
        if response and response.status_code == 200:
            for fork in response.json():
                forks.append(
                    {
                        "name": fork.get("full_name", ""),
                        "owner": fork.get("owner", {}).get("login", ""),
                        "html_url": fork.get("html_url", ""),
                        "stargazers_count": fork.get("stargazers_count", 0),
                    }
                )
        return forks

    # CI/CD WORKFLOWS METHOD COMMENTED OUT - User requested removal
    # def get_workflows(self, owner, repo):
    #     """Get GitHub Actions workflows"""
    #     workflows = []
    #     response = self._request(f"/repos/{owner}/{repo}/actions/workflows")
    #     if response and response.status_code == 200:
    #         data = response.json()
    #         for workflow in data.get("workflows", []):
    #             workflows.append({"name": workflow.get("name", ""), "path": workflow.get("path", ""), "state": workflow.get("state", ""), "html_url": workflow.get("html_url", "")})
    #     return workflows

    def get_workflows(self, _owner, _repo):
        """Get GitHub Actions workflows - DISABLED BY USER REQUEST"""
        return []  # Always return empty list to skip workflow processing

    def _get_simple_users(self, endpoint):
        """Get simple user list"""
        users = []
        response = self._request(f"{endpoint}?per_page=100")
        if response and response.status_code == 200:
            for user in response.json():
                users.append({"login": user.get("login", ""), "html_url": user.get("html_url", ""), "avatar_url": user.get("avatar_url", "")})
        return users

    def get_pull_request(self, owner, repo, pr_number):
        """Get specific pull request"""
        response = self._request(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        if response and response.status_code == 200:
            return response.json()
        return None

    def get_all_issues(self, owner, repo):
        """Get all issues from repository"""
        all_issues = []
        page = 1
        while page <= 10:  # Limit to 10 pages
            response = self._request(f"/repos/{owner}/{repo}/issues?state=all&page={page}&per_page=100")
            if not response or response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            # Filter out pull requests (GitHub API includes PRs in issues)
            issues = [issue for issue in data if not issue.get("pull_request")]
            all_issues.extend(issues)

            page += 1
            if len(data) < 100:
                break

        return all_issues

    def get_all_pull_requests(self, owner, repo):
        """Get all pull requests from repository"""
        all_prs = []
        page = 1
        while page <= 10:  # Limit to 10 pages
            response = self._request(f"/repos/{owner}/{repo}/pulls?state=all&page={page}&per_page=100")
            if not response or response.status_code != 200:
                break

            data = response.json()
            if not data:
                break

            all_prs.extend(data)

            page += 1
            if len(data) < 100:
                break

        return all_prs
