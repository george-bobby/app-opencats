"""
GitLab API Client
"""

import time

import requests

from apps.gitlab.config.settings import settings
from common.logger import logger


class GitLabClient:
    """GitLab API client"""

    def __init__(self):
        self.token = settings.GITLAB_TOKEN
        self.base_url = f"{settings.GITLAB_URL}/api/v4"

    def _request(self, method, endpoint, data=None, timeout=30):
        """Make GitLab API request"""
        headers = {"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"}
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=timeout)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=timeout)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return response
        except requests.exceptions.Timeout:
            logger.fail(f"GitLab API timeout after {timeout}s: {method} {endpoint}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.fail(f"GitLab API connection error: {e}")
            return None
        except Exception as e:
            logger.fail(f"GitLab API error: {e}")
            return None

    def delete_project_if_exists(self, project_name):
        """Delete existing project if it exists"""
        response = self._request("GET", "/projects")
        if response and response.status_code == 200:
            projects = response.json()
            for project in projects:
                if project["name"] == project_name:
                    project_id = project["id"]

                    delete_response = self._request("DELETE", f"/projects/{project_id}")
                    if delete_response and delete_response.status_code == 202:
                        time.sleep(3)
                        return True
        return True

    def start_import(self, import_data):
        """Start GitHub import"""
        response = self._request("POST", "/import/github", import_data, timeout=120)

        if response and response.status_code == 201:
            data = response.json()
            project_id = data.get("id")
            return project_id
        elif response and response.status_code == 422:
            # Try with alternative name
            import_data["new_name"] = f"{import_data['new_name']}_imported"
            response = self._request("POST", "/import/github", import_data, timeout=120)

            if response and response.status_code == 201:
                data = response.json()
                project_id = data.get("id")
                return project_id

        # Enhanced error reporting
        if response:
            try:
                error_data = response.json()
                logger.fail(f"Import failed - Status: {response.status_code}, Error: {error_data}")
            except Exception:
                logger.fail(f"Import failed - Status: {response.status_code}, Response: {response.text}")
        else:
            logger.fail("Import failed - No response from GitLab")

        return None

    def get_import_progress(self, project_id):
        """Get import progress"""
        response = self._request("GET", f"/projects/{project_id}")
        if not response or response.status_code != 200:
            return None

        data = response.json()

        # Get basic stats
        stats = {"status": data.get("import_status", "unknown"), "name": data.get("name", "Unknown"), "issues": 0, "mrs": 0}

        # Get counts
        response = self._request("GET", f"/projects/{project_id}/issues?per_page=1")
        if response and response.status_code == 200:
            total = response.headers.get("X-Total")
            if total:
                stats["issues"] = int(total)

        response = self._request("GET", f"/projects/{project_id}/merge_requests?per_page=1")
        if response and response.status_code == 200:
            total = response.headers.get("X-Total")
            if total:
                stats["mrs"] = int(total)

        return stats

    def get_users(self):
        """Get GitLab users"""
        gitlab_users = {}

        response = self._request("GET", "/users?per_page=100")
        if response and response.status_code == 200:
            for user in response.json():
                gitlab_users[user["username"]] = {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "email": user.get("email", ""),
                    "avatar_url": user.get("avatar_url"),
                    "web_url": user.get("web_url"),
                }

        return gitlab_users

    def create_user(self, user_data):
        """Create GitLab user"""
        response = self._request("POST", "/users", user_data)

        if response and response.status_code == 201:
            return {"success": True, "user": response.json()}
        else:
            error_msg = response.text if response else "No response"
            return {"success": False, "error": error_msg}

    def create_file(self, project_id, file_path, content, commit_message):
        """Create file in repository"""
        file_data = {"branch": "main", "commit_message": commit_message, "content": content, "encoding": "text"}

        response = self._request("POST", f"/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}", file_data)
        return response and response.status_code == 201

    def get_available_import_sources(self):
        """Get available import sources"""
        response = self._request("GET", "/application/settings")

        if response and response.status_code == 200:
            data = response.json()
            return data.get("import_sources", [])

        return []
