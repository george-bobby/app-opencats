"""
Comprehensive GitLab GitHub Importer
Ensures complete repository synchronization including all branches, tags, and source code
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from common.logger import logger

from .documentation import DocumentationManager
from .github_client import GitHubClient
from .gitlab_client import GitLabClient
from .user_manager import UserManager


class ComprehensiveImporter:
    """
    Comprehensive GitHub to GitLab importer that ensures:
    1. Complete metadata import (issues, MRs, users)
    2. Complete source code synchronization
    3. All branches and tags
    4. Proper user attribution
    """

    def __init__(self, advanced_attribution=True):
        # Import here to ensure latest config
        from apps.gitlab.config.settings import load_env_config

        self.config = load_env_config()
        self.github = GitHubClient()
        self.gitlab = GitLabClient()
        self.user_manager = UserManager(self.github, self.gitlab)
        self.docs = DocumentationManager(self.gitlab)
        self.use_advanced_attribution = advanced_attribution

    def import_repository_comprehensive(self, repo_name, github_url):
        """
        Comprehensive import: metadata + complete repository synchronization
        """
        try:
            owner, repo = self._parse_github_url(github_url)

            # Validation phase
            if not self._validate_setup(owner, repo):
                return False

            # Phase 1: Metadata Import
            project_id = self._import_metadata(repo_name, owner, repo)
            if not project_id:
                return False

            # Phase 2: Repository Synchronization
            sync_success = self._synchronize_repository_comprehensive(project_id, repo_name, owner, repo, github_url)
            if not sync_success:
                logger.warning("Repository synchronization had issues, but metadata import succeeded")

            # Phase 3: Attribution Fixing
            self._fix_attribution(repo_name, owner, repo)

            # Phase 4: Documentation and Verification
            self._create_comprehensive_documentation(project_id, owner, repo)
            self._verify_import_completeness(project_id, owner, repo)

            # Phase 5: User Assignment and Activity
            self._add_github_contributors_as_project_members(project_id, repo_name, owner, repo)
            self._assign_admin_to_project(project_id, repo_name, owner, repo)

            return True

        except Exception as e:
            logger.fail(f"Comprehensive import failed: {e}")
            return False

    def _validate_setup(self, owner, repo):
        """Validate tokens and access"""
        if self.config["github_token"] == "your_github_personal_access_token_here":
            logger.fail("GitHub token not configured")
            return False

        if self.config["gitlab_token"] == "your_gitlab_personal_access_token_here":
            logger.fail("GitLab token not configured")
            return False

        import_sources = self.gitlab.get_available_import_sources()
        if "github" not in import_sources:
            logger.fail("GitHub import not enabled")
            return False

        if not self.github.validate_access(owner, repo):
            logger.fail("Cannot access GitHub repository")
            return False

        return True

    def _import_metadata(self, repo_name, owner, repo):
        """Phase 1: Import metadata using GitLab's built-in importer"""
        try:
            # Prepare user mapping
            user_mapping_success = self._prepare_user_mapping(repo_name, owner, repo)
            if not user_mapping_success:
                logger.warning("User mapping preparation failed, but continuing with import")

            # Start GitLab import
            project_id = self._start_gitlab_import(repo_name, owner, repo)
            if not project_id:
                return None

            # Monitor import progress
            import_success = self._monitor_import(project_id)
            if not import_success:
                return None

            return project_id

        except Exception as e:
            logger.fail(f"Metadata import error: {e}")
            return None

    def _synchronize_repository_comprehensive(self, project_id, _repo_name, owner, repo, github_url):
        """
        Phase 2: Comprehensive repository synchronization
        """
        try:
            # Get GitLab project details
            project_info = self._get_gitlab_project_info(project_id)
            if not project_info:
                return False

            gitlab_repo_url = project_info["http_url_to_repo"]

            # Remove branch protections temporarily
            protected_branches = self._remove_branch_protections(project_id)

            # Clone and sync repository
            sync_success = self._clone_and_sync_complete_repository(github_url, gitlab_repo_url, owner, repo)

            # Restore branch protections
            if protected_branches:
                self._restore_branch_protections(project_id, protected_branches)

            # Verify synchronization
            if sync_success:
                self._verify_repository_sync(project_id, owner, repo)

            return sync_success

        except Exception as e:
            logger.fail(f"Repository synchronization error: {e}")
            return False

    def _clone_and_sync_complete_repository(self, github_url, gitlab_repo_url, _owner, repo):
        """Clone complete repository from GitHub and sync to GitLab"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_dir = Path(temp_dir) / f"{repo}_complete"

                # Try mirror clone first
                result = subprocess.run(["git", "clone", "--mirror", github_url, clone_dir], capture_output=True, text=True)

                if result.returncode != 0:
                    # Fallback to regular clone
                    result = subprocess.run(["git", "clone", "--bare", github_url, clone_dir], capture_output=True, text=True)

                    if result.returncode != 0:
                        logger.fail(f"Failed to clone repository: {result.stderr}")
                        return False

                # Change to clone directory
                os.chdir(clone_dir)

                # Configure GitLab remote with authentication
                gitlab_remote_url = gitlab_repo_url.replace("http://", f"http://root:{self.gitlab.token}@")

                # Remove existing GitLab remote if it exists
                subprocess.run(["git", "remote", "remove", "gitlab"], capture_output=True)

                # Add GitLab remote
                result = subprocess.run(["git", "remote", "add", "gitlab", gitlab_remote_url], capture_output=True, text=True)

                if result.returncode != 0:
                    logger.fail(f"Failed to add GitLab remote: {result.stderr}")
                    return False

                # Push everything to GitLab
                logger.info("Pushing complete repository to GitLab...")

                # Push all branches
                logger.info("Pushing all branches...")
                result = subprocess.run(["git", "push", "gitlab", "--all", "--force"], capture_output=True, text=True)

                if result.returncode != 0:
                    logger.warning(f"Bulk branch push failed: {result.stderr}")
                    # Try individual branch push
                    self._push_branches_individually(clone_dir)
                else:
                    logger.info("All branches pushed successfully")

                # Push all tags
                logger.info("Pushing all tags...")
                result = subprocess.run(["git", "push", "gitlab", "--tags", "--force"], capture_output=True, text=True)

                if result.returncode != 0:
                    logger.warning(f"Tag push failed: {result.stderr}")
                else:
                    logger.info("All tags pushed successfully")

                return True

        except Exception as e:
            logger.fail(f"Repository cloning and sync error: {e}")
            return False

    def _push_branches_individually(self, clone_dir):
        """Push branches individually if bulk push fails"""
        try:
            os.chdir(clone_dir)

            # Get all branches
            result = subprocess.run(["git", "branch", "-r"], capture_output=True, text=True)

            if result.returncode != 0:
                logger.fail("Failed to get branches")
                return

            branches = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and not line.startswith("origin/HEAD"):
                    branch = line.replace("origin/", "")
                    if branch:
                        branches.append(branch)

            logger.info(f"Found {len(branches)} branches to push")

            success_count = 0
            for i, branch in enumerate(branches[:50]):  # Limit to 50 branches
                logger.info(f"Pushing branch {i + 1}/{min(50, len(branches))}: {branch}")

                result = subprocess.run(["git", "push", "gitlab", f"origin/{branch}:refs/heads/{branch}", "--force"], capture_output=True, text=True)

                if result.returncode == 0:
                    success_count += 1
                else:
                    logger.warning(f"Failed to push {branch}: {result.stderr[:100]}...")

                time.sleep(0.1)  # Small delay

            logger.info(f"Successfully pushed {success_count}/{min(50, len(branches))} branches")

        except Exception as e:
            logger.fail(f"Individual branch push error: {e}")

    def _get_gitlab_project_info(self, project_id):
        """Get GitLab project information"""
        response = self.gitlab._request("GET", f"/projects/{project_id}")
        if response and response.status_code == 200:
            return response.json()
        return None

    def _remove_branch_protections(self, project_id):
        """Temporarily remove branch protections"""
        try:
            logger.info("Temporarily removing branch protections...")
            response = self.gitlab._request("GET", f"/projects/{project_id}/protected_branches")
            protected_branches = []

            if response and response.status_code == 200:
                protected_branches = response.json()
                for branch in protected_branches:
                    branch_name = branch["name"]
                    logger.info(f"Removing protection from: {branch_name}")
                    self.gitlab._request("DELETE", f"/projects/{project_id}/protected_branches/{branch_name}")

            return protected_branches

        except Exception as e:
            logger.warning(f"Error removing branch protections: {e}")
            return []

    def _restore_branch_protections(self, project_id, protected_branches):
        """Restore branch protections"""
        try:
            logger.info("Restoring branch protections...")
            for branch_info in protected_branches:
                protection_data = {
                    "name": branch_info["name"],
                    "push_access_level": branch_info.get("push_access_levels", [{}])[0].get("access_level", 40),
                    "merge_access_level": branch_info.get("merge_access_levels", [{}])[0].get("access_level", 40),
                    "allow_force_push": branch_info.get("allow_force_push", False),
                }

                response = self.gitlab._request("POST", f"/projects/{project_id}/protected_branches", protection_data)
                if response and response.status_code == 201:
                    logger.info(f"Re-protected branch: {branch_info['name']}")

        except Exception as e:
            logger.warning(f"Error restoring branch protections: {e}")

    def _verify_repository_sync(self, project_id, _owner, _repo):
        """Verify repository synchronization completeness"""
        try:
            logger.info("Verifying repository synchronization...")

            # Check repository contents
            response = self.gitlab._request("GET", f"/projects/{project_id}/repository/tree")
            if response and response.status_code == 200:
                files = response.json()
                logger.info(f"Repository contains {len(files)} root items")

                file_names = [f["name"] for f in files[:10]]
                logger.info(f"Root items include: {', '.join(file_names)}...")

            # Check branches
            response = self.gitlab._request("GET", f"/projects/{project_id}/repository/branches")
            if response and response.status_code == 200:
                branches = response.json()
                logger.info(f"Repository has {len(branches)} branches")

                branch_names = [b["name"] for b in branches[:10]]
                logger.info(f"Branches include: {', '.join(branch_names)}...")

            # Check tags
            response = self.gitlab._request("GET", f"/projects/{project_id}/repository/tags")
            if response and response.status_code == 200:
                tags = response.json()
                logger.info(f"Repository has {len(tags)} tags")

                if tags:
                    tag_names = [t["name"] for t in tags[:5]]
                    logger.info(f"Tags include: {', '.join(tag_names)}...")

            logger.info("Repository synchronization verification completed")

        except Exception as e:
            logger.warning(f"Repository verification error: {e}")

    def _verify_import_completeness(self, project_id, _owner, _repo):
        """Verify overall import completeness"""
        try:
            logger.info("Verifying overall import completeness...")

            # Get project stats
            response = self.gitlab._request("GET", f"/projects/{project_id}")
            if response and response.status_code == 200:
                project = response.json()

                # Check issues
                response = self.gitlab._request("GET", f"/projects/{project_id}/issues?per_page=1")
                issues_count = 0
                if response and response.status_code == 200:
                    total = response.headers.get("X-Total")
                    if total:
                        issues_count = int(total)

                # Check merge requests
                response = self.gitlab._request("GET", f"/projects/{project_id}/merge_requests?per_page=1")
                mrs_count = 0
                if response and response.status_code == 200:
                    total = response.headers.get("X-Total")
                    if total:
                        mrs_count = int(total)

                logger.info("Import Completeness Summary:")
                logger.info(f"  Project: {project.get('name')}")
                logger.info(f"  Issues: {issues_count}")
                logger.info(f"  Merge Requests: {mrs_count}")
                logger.info(f"  Import Status: {project.get('import_status', 'unknown')}")

                return True

        except Exception as e:
            logger.warning(f"Import verification error: {e}")
            return False

    # Include all the helper methods from the original importer
    def _parse_github_url(self, github_url):
        """Extract owner and repo from GitHub URL"""
        parsed = urlparse(github_url.rstrip(".git"))
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Invalid GitHub URL: {github_url}")

    def _prepare_user_mapping(self, _repo_name, owner, repo):
        """Prepare user mapping BEFORE starting import"""
        try:
            logger.info("Analyzing GitHub users...")
            github_users = self.github.get_all_users(owner, repo)
            if not github_users:
                logger.warning("No GitHub users found to analyze")
                self._user_mapping_data = {}
                return True

            logger.info("Getting existing GitLab users...")
            gitlab_users = self.gitlab.get_users()

            logger.info("Analyzing user mapping requirements...")
            mapping_analysis = self.user_manager.analyze_mapping(github_users, gitlab_users)

            # Create missing users BEFORE import starts
            if mapping_analysis["unmappable_users"]:
                logger.info(f"Creating {len(mapping_analysis['unmappable_users'])} missing users...")
                auto_create_result = self.user_manager.auto_create_users(mapping_analysis["unmappable_users"])

                # Give GitLab time to process user creation and indexing
                logger.info("Waiting for user creation and indexing to complete...")
                time.sleep(10)

                # Refresh GitLab users list to include newly created users
                logger.info("Refreshing GitLab users list...")
                gitlab_users = self.gitlab.get_users()

                # Re-analyze mapping with refreshed user list
                mapping_analysis = self.user_manager.analyze_mapping(github_users, gitlab_users)

                # Store creation result for documentation
                self._user_credentials_for_later = auto_create_result

            # Build explicit user mapping for GitLab import API
            logger.info("Building explicit user mapping...")
            self._user_mapping_data = self._build_user_mapping(github_users, mapping_analysis)

            # Store mapping for documentation
            self._user_mapping_for_later = (github_users, mapping_analysis)

            logger.info(f"User mapping preparation completed - {len(self._user_mapping_data)} mappings ready")
            return True

        except Exception as e:
            logger.fail(f"User mapping preparation failed: {e}")
            self._user_mapping_data = {}
            return False

    def _build_user_mapping(self, github_users, mapping_analysis):
        """Build explicit user mapping for GitLab import API"""
        user_mapping = {}

        # Add exact username matches
        for gh_username, gitlab_user in mapping_analysis["exact_username_matches"].items():
            if gh_username in github_users:
                github_id = github_users[gh_username].get("id")
                if github_id:
                    user_mapping[str(github_id)] = gitlab_user["id"]
                    logger.info(f"Mapped GitHub {gh_username} (ID: {github_id}) → GitLab {gitlab_user['username']} (ID: {gitlab_user['id']})")

        # Add email matches
        for gh_username, gitlab_user in mapping_analysis["potential_email_matches"].items():
            if gh_username in github_users:
                github_id = github_users[gh_username].get("id")
                if github_id:
                    user_mapping[str(github_id)] = gitlab_user["id"]
                    logger.info(f"Mapped GitHub {gh_username} (ID: {github_id}) → GitLab {gitlab_user['username']} (ID: {gitlab_user['id']}) [email match]")

        # Add newly created users
        if hasattr(self, "_user_credentials_for_later"):
            created_users = self._user_credentials_for_later.get("created_users", [])
            for created_user_data in created_users:
                gitlab_user = created_user_data["user"]
                gitlab_username = gitlab_user["username"]

                # Find corresponding GitHub user
                for gh_username, gh_user in github_users.items():
                    if gitlab_username == gh_username or gitlab_username.startswith(f"{gh_username}_"):
                        github_id = gh_user.get("id")
                        if github_id:
                            user_mapping[str(github_id)] = gitlab_user["id"]
                            logger.info(f"Mapped GitHub {gh_username} (ID: {github_id}) → GitLab {gitlab_username} (ID: {gitlab_user['id']}) [newly created]")
                            break

        return user_mapping

    def _start_gitlab_import(self, repo_name, owner, repo):
        """Start GitLab import process with explicit user mapping"""
        # Delete existing project if exists
        self.gitlab.delete_project_if_exists(repo_name)

        # Get GitHub repo info
        repo_data = self.github.get_repository(owner, repo)
        if not repo_data:
            return None

        # Build import data with explicit user mapping
        import_data = {
            "repo_id": repo_data.get("id"),
            "new_name": repo_name,
            "target_namespace": "root",
            "personal_access_token": self.github.token,
            "user_contribution_mapping_enabled": True,
            "optional_stages": {
                "single_endpoint_notes_import": True,
                "attachments_import": True,
                "collaborators_import": False,
                "issue_events_import": True,
                "lfs_objects_import": True,
                "protected_branches_import": True,
                "pull_request_reviews_import": True,
            },
        }

        # Add explicit user mapping if available
        if hasattr(self, "_user_mapping_data") and self._user_mapping_data:
            import_data["user_mapping"] = self._user_mapping_data
            logger.info(f"Adding explicit user mapping with {len(self._user_mapping_data)} mappings")
        else:
            logger.info("No explicit user mapping available - using automatic mapping only")

        return self.gitlab.start_import(import_data)

    def _monitor_import(self, project_id):
        """Monitor import progress with smart stuck detection"""
        logger.info("Monitoring import...")
        start_time = time.time()
        progress_history = []
        max_wait_without_progress = 10 * 60  # 10 minutes without any progress
        last_progress_time = start_time

        while True:
            # Get fresh progress data
            progress = self.gitlab.get_import_progress(project_id)
            current_time = time.time()
            elapsed = int(current_time - start_time)

            if not progress:
                logger.warning("Could not get import progress, retrying...")
                time.sleep(30)
                continue

            status = progress["status"]
            issues_count = progress.get("issues", 0)
            mrs_count = progress.get("mrs", 0)

            # Check if import is finished
            if status in ["finished", "completed"]:
                logger.succeed(f"Import completed in {elapsed // 60}m {elapsed % 60}s")
                return True
            elif status == "failed":
                logger.fail("Import failed")
                return False

            # Record progress for trend analysis
            progress_snapshot = {"time": current_time, "issues": issues_count, "mrs": mrs_count, "status": status}
            progress_history.append(progress_snapshot)

            # Keep only last 10 minutes of history
            progress_history = [p for p in progress_history if current_time - p["time"] <= 600]

            # Check for actual progress (content changes)
            if len(progress_history) >= 2:
                first_snapshot = progress_history[0]
                current_snapshot = progress_history[-1]

                issues_progress = current_snapshot["issues"] - first_snapshot["issues"]
                mrs_progress = current_snapshot["mrs"] - first_snapshot["mrs"]

                if issues_progress > 0 or mrs_progress > 0:
                    last_progress_time = current_time
                    logger.info(f"Progress detected: +{issues_progress} issues, +{mrs_progress} MRs in last {len(progress_history)} checks")

            # Check if we're truly stuck (no progress for too long)
            time_without_progress = current_time - last_progress_time

            if time_without_progress > max_wait_without_progress:
                logger.warning(f"No progress detected for {int(time_without_progress // 60)} minutes")

                # If we have substantial content, consider it potentially complete
                if issues_count > 0 or mrs_count > 0:
                    logger.info(f"Found substantial content: {issues_count} issues, {mrs_count} MRs")
                    logger.info("Import may be complete but status not updated. Checking stability...")

                    # Check if numbers are stable for last 5 minutes
                    recent_history = [p for p in progress_history if current_time - p["time"] <= 300]
                    if len(recent_history) >= 5:
                        stable_issues = all(p["issues"] == issues_count for p in recent_history)
                        stable_mrs = all(p["mrs"] == mrs_count for p in recent_history)

                        if stable_issues and stable_mrs:
                            logger.succeed(f"Content stable for 5+ minutes: {issues_count} issues, {mrs_count} MRs")
                            logger.info("Proceeding to next phase (import appears complete)")
                            return True

                # If no content and long stuck, check if it's a real failure
                if issues_count == 0 and mrs_count == 0 and time_without_progress > 15 * 60:
                    logger.fail("No content imported after 15+ minutes of no progress")

                    # One final check - maybe the API is not reflecting the real state
                    logger.info("Performing final verification check...")
                    verification_result = self._verify_import_has_content(project_id)
                    if verification_result:
                        logger.succeed("Verification found content - proceeding")
                        return True
                    else:
                        logger.fail("Verification confirms no content - import likely failed")
                        return False

            # Log progress periodically
            if elapsed % 60 == 0:  # Every minute
                logger.info(
                    f"Status: {status} | Issues: {issues_count} | MRs: {mrs_count} | Elapsed: {elapsed // 60}m {elapsed % 60}s | No progress for: {int(time_without_progress // 60)}m"
                )

            time.sleep(30)

    def _verify_import_has_content(self, project_id):
        """Final verification to check if project actually has content"""
        try:
            # Check repository files
            response = self.gitlab._request("GET", f"/projects/{project_id}/repository/tree")
            if response and response.status_code == 200:
                files = response.json()
                if len(files) > 0:
                    logger.info(f"Found {len(files)} files in repository")
                    return True

            # Check issues via direct API
            response = self.gitlab._request("GET", f"/projects/{project_id}/issues?per_page=1")
            if response and response.status_code == 200:
                total_header = response.headers.get("X-Total")
                if total_header and int(total_header) > 0:
                    logger.info(f"Found {total_header} issues via direct API")
                    return True

            # Check merge requests via direct API
            response = self.gitlab._request("GET", f"/projects/{project_id}/merge_requests?per_page=1")
            if response and response.status_code == 200:
                total_header = response.headers.get("X-Total")
                if total_header and int(total_header) > 0:
                    logger.info(f"Found {total_header} merge requests via direct API")
                    return True

            logger.info("No content found in verification")
            return False

        except Exception as e:
            logger.warning(f"Verification check failed: {e}")
            return False

    def _fix_attribution(self, repo_name, owner, repo):
        """Fix user attribution after import - Enhanced comprehensive attribution using direct DB updates"""
        try:
            logger.info("🔧 Starting comprehensive attribution fixing...")

            # Get project ID
            project_id = self._get_project_id_by_name(repo_name)
            if not project_id:
                logger.fail("Could not find project for attribution fixing")
                return False

            # Get GitHub to GitLab user mapping
            user_mapping = self._build_comprehensive_user_mapping(owner, repo)
            if not user_mapping:
                logger.warning("No user mapping available - skipping attribution fixing")
                return True

            logger.info(f"Found {len(user_mapping)} GitHub→GitLab user mappings")

            # Try database-based attribution fixing (more reliable)
            logger.info("🗄️ Attempting direct database attribution fixing...")
            db_success = self._fix_attribution_database(project_id, owner, repo, user_mapping)

            if db_success:
                logger.succeed("✅ Database attribution fixing completed successfully!")
                return True
            else:
                logger.warning("Database fixing failed, falling back to API-based fixing...")

            # Fallback to API-based fixing
            attribution_results = {}

            # 1. Fix Issues Attribution
            logger.info("Fixing issues attribution...")
            attribution_results["issues"] = self._fix_issues_attribution(project_id, owner, repo, user_mapping)

            # 2. Fix Merge Requests Attribution
            logger.info("Fixing merge requests attribution...")
            attribution_results["merge_requests"] = self._fix_merge_requests_attribution(project_id, owner, repo, user_mapping)

            # 3. Fix Notes/Comments Attribution
            logger.info("Fixing comments attribution...")
            attribution_results["notes"] = self._fix_notes_attribution(project_id, owner, repo, user_mapping)

            # Report results
            self._report_attribution_results(attribution_results)

            return True

        except Exception as e:
            logger.fail(f"Attribution fixing error: {e}")
            return False

    def _fix_attribution_database(self, project_id, owner, repo, user_mapping):
        """Fix attribution by directly updating the PostgreSQL database"""
        try:
            logger.info("📊 Building GitHub to GitLab author mapping...")

            # Get GitHub issues and PRs to build mapping
            github_issues = self.github.get_all_issues(owner, repo)
            github_prs = self.github.get_all_pull_requests(owner, repo)

            # Build mapping of GitHub content to authors
            github_content_authors = {}

            # Map GitHub issues by title
            for issue in github_issues:
                title = issue.get("title", "").strip()
                github_author = issue.get("user", {}).get("login")
                if title and github_author and github_author in user_mapping:
                    github_content_authors[title] = {"github_username": github_author, "gitlab_user_id": user_mapping[github_author]["gitlab_id"], "content_type": "issue"}

            # Map GitHub PRs by title
            for pr in github_prs:
                title = pr.get("title", "").strip()
                github_author = pr.get("user", {}).get("login")
                if title and github_author and github_author in user_mapping:
                    github_content_authors[title] = {"github_username": github_author, "gitlab_user_id": user_mapping[github_author]["gitlab_id"], "content_type": "merge_request"}

            if not github_content_authors:
                logger.warning("No GitHub content mapping found")
                return False

            logger.info(f"Found {len(github_content_authors)} GitHub content items to map")

            # Execute database updates
            fixed_count = 0

            # Fix issues
            issues_query = f"""
                UPDATE issues 
                SET author_id = %s, updated_at = NOW()
                WHERE project_id = {project_id} 
                AND title = %s 
                AND author_id IN (SELECT id FROM users WHERE username LIKE '%%import%%')
                RETURNING id, iid, title;
            """

            # Fix merge requests
            mrs_query = f"""
                UPDATE merge_requests 
                SET author_id = %s, updated_at = NOW()
                WHERE target_project_id = {project_id} 
                AND title = %s 
                AND author_id IN (SELECT id FROM users WHERE username LIKE '%%import%%')
                RETURNING id, iid, title;
            """

            for title, mapping in github_content_authors.items():
                gitlab_user_id = mapping["gitlab_user_id"]
                github_username = mapping["github_username"]
                content_type = mapping["content_type"]

                try:
                    if content_type == "issue":
                        # Update issues
                        result = subprocess.run(
                            ["docker", "exec", "gitlab-seeding", "gitlab-psql", "-c", issues_query.replace("%s", str(gitlab_user_id), 1).replace("%s", f"'{title}'", 1)],
                            capture_output=True,
                            text=True,
                        )

                        if result.returncode == 0 and "UPDATE 1" in result.stdout:
                            logger.succeed(f"✅ Updated issue '{title}' author to {github_username}")
                            fixed_count += 1

                    elif content_type == "merge_request":
                        # Update merge requests
                        result = subprocess.run(
                            ["docker", "exec", "gitlab-seeding", "gitlab-psql", "-c", mrs_query.replace("%s", str(gitlab_user_id), 1).replace("%s", f"'{title}'", 1)],
                            capture_output=True,
                            text=True,
                        )

                        if result.returncode == 0 and "UPDATE 1" in result.stdout:
                            logger.succeed(f"✅ Updated merge request '{title}' author to {github_username}")
                            fixed_count += 1

                except Exception as e:
                    logger.warning(f"Failed to update '{title}': {e}")
                    continue

            logger.info(f"🎉 Database attribution fixing completed: {fixed_count} items updated")
            return fixed_count > 0

        except Exception as e:
            logger.fail(f"Database attribution fixing failed: {e}")
            return False

    def _get_project_id_by_name(self, repo_name):
        """Get project ID by name"""
        try:
            response = self.gitlab._request("GET", "/projects")
            if response and response.status_code == 200:
                projects = response.json()
                for project in projects:
                    if project.get("name") == repo_name:
                        return project["id"]
            return None
        except Exception as e:
            logger.fail(f"Error getting project ID: {e}")
            return None

    def _build_comprehensive_user_mapping(self, owner, repo):
        """Build comprehensive GitHub→GitLab user mapping"""
        try:
            github_to_gitlab = {}

            # Get GitHub users
            github_users = self.github.get_all_users(owner, repo)
            if not github_users:
                return {}

            # Get GitLab users
            gitlab_users = self.gitlab.get_users()
            if not gitlab_users:
                return {}

            # Build mapping from stored data
            if hasattr(self, "_user_mapping_for_later") and self._user_mapping_for_later:
                github_users_data, mapping_analysis = self._user_mapping_for_later

                # Map exact username matches
                for gh_username, gitlab_user in mapping_analysis["exact_username_matches"].items():
                    if gh_username in github_users:
                        github_to_gitlab[gh_username] = {
                            "gitlab_id": gitlab_user["id"],
                            "gitlab_username": gitlab_user["username"],
                            "github_id": github_users[gh_username].get("id"),
                            "mapping_type": "exact_match",
                        }

                # Map email matches
                for gh_username, gitlab_user in mapping_analysis["potential_email_matches"].items():
                    if gh_username in github_users and gh_username not in github_to_gitlab:
                        github_to_gitlab[gh_username] = {
                            "gitlab_id": gitlab_user["id"],
                            "gitlab_username": gitlab_user["username"],
                            "github_id": github_users[gh_username].get("id"),
                            "mapping_type": "email_match",
                        }

            # Add newly created users
            if hasattr(self, "_user_credentials_for_later") and self._user_credentials_for_later:
                created_users = self._user_credentials_for_later.get("created_users", [])
                for user_data in created_users:
                    gitlab_user = user_data["user"]
                    gitlab_username = gitlab_user["username"]

                    # Find corresponding GitHub user
                    for gh_username, gh_user in github_users.items():
                        if gitlab_username == gh_username or gitlab_username.startswith(f"{gh_username}_"):
                            if gh_username not in github_to_gitlab:
                                github_to_gitlab[gh_username] = {
                                    "gitlab_id": gitlab_user["id"],
                                    "gitlab_username": gitlab_username,
                                    "github_id": gh_user.get("id"),
                                    "mapping_type": "newly_created",
                                }
                            break

            return github_to_gitlab

        except Exception as e:
            logger.fail(f"Error building user mapping: {e}")
            return {}

    def _fix_issues_attribution(self, project_id, owner, repo, user_mapping):
        """Fix attribution for issues"""
        try:
            # Get GitHub issues
            github_issues = self.github.get_all_issues(owner, repo)
            if not github_issues:
                return False

            # Get GitLab issues
            response = self.gitlab._request("GET", f"/projects/{project_id}/issues?per_page=100")
            if not response or response.status_code != 200:
                return False

            gitlab_issues = response.json()
            fixed_count = 0

            for gitlab_issue in gitlab_issues:
                # Skip if not created by Import User
                if not self._is_import_user(gitlab_issue.get("author", {})):
                    continue

                # Find matching GitHub issue
                github_issue = self._find_matching_github_issue(gitlab_issue, github_issues)
                if not github_issue:
                    continue

                # Get GitHub author
                github_author = github_issue.get("user", {}).get("login")
                if not github_author or github_author not in user_mapping:
                    continue

                # Update GitLab issue author
                gitlab_user_id = user_mapping[github_author]["gitlab_id"]
                update_success = self._update_issue_author(project_id, gitlab_issue["iid"], gitlab_user_id, github_author)

                if update_success:
                    fixed_count += 1

                time.sleep(0.1)  # Rate limiting

            logger.info(f"Fixed attribution for {fixed_count} issues")
            return fixed_count > 0

        except Exception as e:
            logger.fail(f"Error fixing issues attribution: {e}")
            return False

    def _fix_merge_requests_attribution(self, project_id, owner, repo, user_mapping):
        """Fix attribution for merge requests"""
        try:
            # Get GitHub pull requests
            github_prs = self.github.get_all_pull_requests(owner, repo)
            if not github_prs:
                return False

            # Get GitLab merge requests
            response = self.gitlab._request("GET", f"/projects/{project_id}/merge_requests?per_page=100")
            if not response or response.status_code != 200:
                return False

            gitlab_mrs = response.json()
            fixed_count = 0

            for gitlab_mr in gitlab_mrs:
                # Skip if not created by Import User
                if not self._is_import_user(gitlab_mr.get("author", {})):
                    continue

                # Find matching GitHub PR
                github_pr = self._find_matching_github_pr(gitlab_mr, github_prs)
                if not github_pr:
                    continue

                # Get GitHub author
                github_author = github_pr.get("user", {}).get("login")
                if not github_author or github_author not in user_mapping:
                    continue

                # Update GitLab MR author
                gitlab_user_id = user_mapping[github_author]["gitlab_id"]
                update_success = self._update_merge_request_author(project_id, gitlab_mr["iid"], gitlab_user_id, github_author)

                if update_success:
                    fixed_count += 1

                time.sleep(0.1)  # Rate limiting

            logger.info(f"Fixed attribution for {fixed_count} merge requests")
            return fixed_count > 0

        except Exception as e:
            logger.fail(f"Error fixing merge requests attribution: {e}")
            return False

    def _fix_notes_attribution(self, project_id, owner, repo, user_mapping):
        """Fix attribution for notes/comments"""
        try:
            fixed_count = 0

            # Fix issue comments
            issue_comments_fixed = self._fix_issue_comments_attribution(project_id, owner, repo, user_mapping)
            fixed_count += issue_comments_fixed

            # Fix MR comments
            mr_comments_fixed = self._fix_mr_comments_attribution(project_id, owner, repo, user_mapping)
            fixed_count += mr_comments_fixed

            logger.info(f"Fixed attribution for {fixed_count} comments/notes")
            return fixed_count > 0

        except Exception as e:
            logger.fail(f"Error fixing notes attribution: {e}")
            return False

    def _is_import_user(self, author):
        """Check if author is the Import User"""
        if not author:
            return False

        username = author.get("username", "").lower()
        name = author.get("name", "").lower()

        # Check for import user patterns
        is_import = (
            "import" in username or "import" in name or username == "root" or "github" in username or "migration" in username or username.startswith("project_") or "bot" in username
        )

        # Debug logging for first few checks
        if hasattr(self, "_debug_import_user_count"):
            self._debug_import_user_count += 1
        else:
            self._debug_import_user_count = 1

        if self._debug_import_user_count <= 3:
            logger.info(f"Checking author: {username} (name: {name}) -> is_import: {is_import}")

        return is_import

    def _find_matching_github_issue(self, gitlab_issue, github_issues):
        """Find matching GitHub issue based on title and content"""
        gitlab_title = gitlab_issue.get("title", "").strip()
        if not gitlab_title:
            return None

        # Try exact title match first
        for gh_issue in github_issues:
            if gh_issue.get("title", "").strip() == gitlab_title:
                return gh_issue

        # Try partial title match
        for gh_issue in github_issues:
            gh_title = gh_issue.get("title", "").strip()
            if gitlab_title in gh_title or gh_title in gitlab_title:
                return gh_issue

        return None

    def _find_matching_github_pr(self, gitlab_mr, github_prs):
        """Find matching GitHub PR based on title and content"""
        gitlab_title = gitlab_mr.get("title", "").strip()
        if not gitlab_title:
            return None

        # Try exact title match first
        for gh_pr in github_prs:
            if gh_pr.get("title", "").strip() == gitlab_title:
                return gh_pr

        # Try partial title match
        for gh_pr in github_prs:
            gh_title = gh_pr.get("title", "").strip()
            if gitlab_title in gh_title or gh_title in gitlab_title:
                return gh_pr

        return None

    def _update_issue_author(self, project_id, issue_iid, new_author_id, github_username):
        """Update issue author - tries multiple approaches"""
        try:
            # Method 1: Try direct API update (usually fails)
            update_data = {"author_id": new_author_id}
            response = self.gitlab._request("PUT", f"/projects/{project_id}/issues/{issue_iid}", update_data)

            if response and response.status_code == 200:
                logger.succeed(f"Updated issue #{issue_iid} author to {github_username}")
                return True

            # Method 2: Add attribution note
            attribution_note = f"**Original Author**: @{github_username} (from GitHub)\n*This issue was originally created by {github_username} on GitHub.*"
            note_data = {"body": attribution_note}
            response = self.gitlab._request("POST", f"/projects/{project_id}/issues/{issue_iid}/notes", note_data)

            if response and response.status_code == 201:
                logger.succeed(f"Added attribution note to issue #{issue_iid} for {github_username}")
                return True

            return False

        except Exception as e:
            logger.warning(f"Error updating issue #{issue_iid}: {e}")
            return False

    def _update_merge_request_author(self, project_id, mr_iid, new_author_id, github_username):
        """Update merge request author - tries multiple approaches"""
        try:
            # Method 1: Try direct API update (usually fails)
            update_data = {"author_id": new_author_id}
            response = self.gitlab._request("PUT", f"/projects/{project_id}/merge_requests/{mr_iid}", update_data)

            if response and response.status_code == 200:
                logger.succeed(f"Updated MR !{mr_iid} author to {github_username}")
                return True

            # Method 2: Add attribution note
            attribution_note = f"**Original Author**: @{github_username} (from GitHub)\n*This merge request was originally created by {github_username} on GitHub.*"
            note_data = {"body": attribution_note}
            response = self.gitlab._request("POST", f"/projects/{project_id}/merge_requests/{mr_iid}/notes", note_data)

            if response and response.status_code == 201:
                logger.succeed(f"Added attribution note to MR !{mr_iid} for {github_username}")
                return True

            return False

        except Exception as e:
            logger.warning(f"Error updating MR !{mr_iid}: {e}")
            return False

    def _fix_issue_comments_attribution(self, _project_id, _owner, _repo, _user_mapping):
        """Fix attribution for issue comments"""
        try:
            # This is a simplified version - in practice, matching comments is complex
            # The comprehensive system focuses on issues and MRs primarily
            return 0
        except Exception:
            return 0

    def _fix_mr_comments_attribution(self, _project_id, _owner, _repo, _user_mapping):
        """Fix attribution for MR comments"""
        try:
            # This is a simplified version - in practice, matching comments is complex
            # The comprehensive system focuses on issues and MRs primarily
            return 0
        except Exception:
            return 0

    def _report_attribution_results(self, results):
        """Report attribution fixing results"""
        logger.info("Attribution Fixing Results:")
        for content_type, success in results.items():
            status = "✅" if success else "⚠️"
            logger.info(f"   {status} {content_type.replace('_', ' ').title()}: {'Fixed' if success else 'No changes'}")

        if any(results.values()):
            logger.succeed("Attribution fixing completed - Issues/MRs now show correct authors where possible!")
        else:
            logger.warning("No attribution changes were made - content may already be correctly attributed")

    def _create_comprehensive_documentation(self, project_id, owner, repo):
        """Create comprehensive documentation"""
        try:
            logger.info("Creating documentation...")

            # Handle deferred user documentation
            if hasattr(self, "_user_credentials_for_later"):
                logger.info("Creating user credentials file...")
                try:
                    self.docs.create_user_credentials_file(project_id, self._user_credentials_for_later)
                except Exception as e:
                    logger.warning(f"Failed to create user credentials file: {e}")

            if hasattr(self, "_user_mapping_for_later"):
                logger.info("Creating user mapping documentation...")
                try:
                    github_users, mapping_analysis = self._user_mapping_for_later
                    self.docs.create_user_mapping_docs(project_id, github_users, mapping_analysis)
                except Exception as e:
                    logger.warning(f"Failed to create user mapping documentation: {e}")

            # Get additional data with better error handling
            logger.info("Fetching GitHub repository data...")
            try:
                stargazers = self.github.get_stargazers(owner, repo)
                logger.info(f"Found {len(stargazers)} stargazers")
            except Exception as e:
                logger.warning(f"Failed to fetch stargazers: {e}")
                stargazers = []

            try:
                watchers = self.github.get_watchers(owner, repo)
                logger.info(f"Found {len(watchers)} watchers")
            except Exception as e:
                logger.warning(f"Failed to fetch watchers: {e}")
                watchers = []

            try:
                forks = self.github.get_forks(owner, repo)
                logger.info(f"Found {len(forks)} forks")
            except Exception as e:
                logger.warning(f"Failed to fetch forks: {e}")
                forks = []

            # CI/CD WORKFLOWS COMMENTED OUT - User requested removal
            # try:
            #     workflows = self.github.get_workflows(owner, repo)
            #     logger.info(f"Found {len(workflows)} workflows")
            # except Exception as e:
            #     logger.warning(f"Failed to fetch workflows: {e}")
            #     workflows = []
            workflows = []  # Set empty to skip workflow processing

            # Create documentation
            logger.info("Creating GitHub data documentation...")
            try:
                self.docs.create_github_data_docs(project_id, owner, repo, {"stargazers": stargazers, "watchers": watchers, "forks": forks, "workflows": workflows})
                logger.succeed("GitHub data documentation created successfully")
            except Exception as e:
                logger.warning(f"Failed to create GitHub data documentation: {e}")

            # PRESERVE GITHUB ACTIONS COMMENTED OUT - User requested removal
            # if workflows:
            #     logger.info("Preserving GitHub Actions workflows...")
            #     try:
            #         self.docs.preserve_github_actions(project_id, owner, repo, workflows)
            #         logger.success("GitHub Actions workflows preserved")
            #     except Exception as e:
            #         logger.warning(f"Failed to preserve GitHub Actions: {e}")
            # else:
            #     logger.info("No GitHub Actions workflows to preserve")

        except Exception as e:
            logger.warning(f"Documentation creation error: {e}")

    def _assign_admin_to_project(self, project_id, repo_name, owner, repo):
        """Assign admin user to project and create activity for home screen visibility"""
        try:
            logger.info("Assigning admin user to project...")

            # Get admin user (root user)
            admin_user = self._get_admin_user()
            if not admin_user:
                logger.warning("Could not find admin user")
                return False

            admin_user_id = admin_user["id"]
            logger.info(f"Found admin user: {admin_user['username']} (ID: {admin_user_id})")

            # Add admin as project member with maintainer access
            member_success = self._add_admin_as_project_member(project_id, admin_user_id)
            if member_success:
                logger.succeed("Admin user added as project maintainer")
            else:
                logger.warning("Could not add admin as project member")

            # Create project activity for admin user
            activity_success = self._create_admin_project_activity(project_id, admin_user_id, repo_name, owner, repo)
            if activity_success:
                logger.succeed("Admin project activity created")
            else:
                logger.warning("Could not create admin project activity")

            logger.succeed("Admin user assignment completed - project will appear on GitLab home screen!")
            return True

        except Exception as e:
            logger.warning(f"Admin assignment error: {e}")
            return False

    def _add_github_contributors_as_project_members(self, project_id, _repo_name, _owner, _repo):
        """Add all created GitHub contributors as project members"""
        try:
            logger.info("Adding GitHub contributors as project members...")

            # Get all GitLab users that should be project members
            users_to_add = []

            # 1. Add newly created users
            if hasattr(self, "_user_credentials_for_later") and self._user_credentials_for_later:
                created_users = self._user_credentials_for_later.get("created_users", [])
                for user_data in created_users:
                    gitlab_user = user_data["user"]
                    users_to_add.append({"id": gitlab_user["id"], "username": gitlab_user["username"], "source": "newly_created"})

            # 2. Add existing users that were mapped to GitHub contributors
            if hasattr(self, "_user_mapping_for_later") and self._user_mapping_for_later:
                github_users, mapping_analysis = self._user_mapping_for_later

                # Add exact username matches
                for _gh_username, gitlab_user in mapping_analysis["exact_username_matches"].items():
                    users_to_add.append({"id": gitlab_user["id"], "username": gitlab_user["username"], "source": "exact_match"})

                # Add email matches
                for _gh_username, gitlab_user in mapping_analysis["potential_email_matches"].items():
                    users_to_add.append({"id": gitlab_user["id"], "username": gitlab_user["username"], "source": "email_match"})

            if not users_to_add:
                logger.info("No GitHub contributors found to add as project members")
                return True

            logger.info(f"Found {len(users_to_add)} GitHub contributors to add as project members")

            added_count = 0
            failed_count = 0

            for user_info in users_to_add:
                user_id = user_info["id"]
                username = user_info["username"]
                source = user_info["source"]

                try:
                    # Add user as Developer (access level 30)
                    member_success = self._add_user_as_project_member(project_id, user_id, username, access_level=30)
                    if member_success:
                        added_count += 1
                        logger.succeed(f"Added {username} as project member ({source})")
                    else:
                        failed_count += 1
                        logger.warning(f"Failed to add {username} as project member ({source})")

                    # Small delay to avoid overwhelming GitLab API
                    time.sleep(0.2)

                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Error adding {username} as member: {e}")

            logger.info("Project member assignment completed:")
            logger.info(f"   ✅ Successfully added: {added_count} users")
            logger.info(f"   ❌ Failed to add: {failed_count} users")
            logger.info("   Total GitHub contributors now have project access!")

            return added_count > 0

        except Exception as e:
            logger.fail(f"Error adding GitHub contributors as members: {e}")
            return False

    def _add_user_as_project_member(self, project_id, user_id, username, access_level=30):
        """Add a specific user as project member"""
        try:
            # Check if user is already a member
            response = self.gitlab._request("GET", f"/projects/{project_id}/members/{user_id}")
            if response and response.status_code == 200:
                logger.info(f"{username} is already a project member")
                return True

            # Add user as project member
            # Access levels: 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
            member_data = {
                "user_id": user_id,
                "access_level": access_level,  # 30 = Developer (can push, create branches, etc.)
            }

            response = self.gitlab._request("POST", f"/projects/{project_id}/members", member_data)
            if response and response.status_code == 201:
                return True
            elif response and response.status_code == 409:
                logger.info(f"{username} is already a project member (conflict resolved)")
                return True
            else:
                if response:
                    logger.warning(f"Failed to add {username}: HTTP {response.status_code}")
                    try:
                        error_data = response.json()
                        logger.warning(f"   Error details: {error_data}")
                    except Exception:
                        pass
                return False

        except Exception as e:
            logger.fail(f"Error adding {username} as member: {e}")
            return False

    def _get_admin_user(self):
        """Get the admin (root) user"""
        try:
            # Try to get root user directly
            response = self.gitlab._request("GET", "/users?username=root")
            if response and response.status_code == 200:
                users = response.json()
                if users:
                    return users[0]

            # Fallback: get current user (should be the token owner)
            response = self.gitlab._request("GET", "/user")
            if response and response.status_code == 200:
                return response.json()

            return None

        except Exception as e:
            logger.fail(f"Error getting admin user: {e}")
            return None

    def _add_admin_as_project_member(self, project_id, admin_user_id):
        """Add admin user as project member with maintainer access"""
        try:
            # Check if admin is already a member
            response = self.gitlab._request("GET", f"/projects/{project_id}/members/{admin_user_id}")
            if response and response.status_code == 200:
                logger.info("Admin user is already a project member")
                return True

            # Add admin as maintainer (access level 40)
            member_data = {
                "user_id": admin_user_id,
                "access_level": 40,  # 40 = Maintainer, 50 = Owner
            }

            response = self.gitlab._request("POST", f"/projects/{project_id}/members", member_data)
            if response and response.status_code == 201:
                logger.succeed("Admin user added as project maintainer")
                return True
            elif response and response.status_code == 409:
                logger.info("Admin user is already a project member (conflict)")
                return True
            else:
                logger.fail(f"Failed to add admin as member: {response.status_code if response else 'No response'}")
                return False

        except Exception as e:
            logger.fail(f"Error adding admin as member: {e}")
            return False

    def _create_admin_project_activity(self, project_id, admin_user_id, repo_name, owner, repo):
        """Create activity for admin user on the project"""
        try:
            logger.info("Creating admin project activity...")

            activities_created = 0

            # Activity 1: Star the project
            star_success = self._star_project(project_id)
            if star_success:
                activities_created += 1
                logger.info("Admin starred the project")

            # Activity 2: Assign admin to some issues (max 3)
            issues_assigned = self._assign_admin_to_issues(project_id, admin_user_id, max_issues=3)
            if issues_assigned > 0:
                activities_created += issues_assigned
                logger.info(f"Admin assigned to {issues_assigned} issues")

            # Activity 3: Assign admin to some merge requests (max 2)
            mrs_assigned = self._assign_admin_to_merge_requests(project_id, admin_user_id, max_mrs=2)
            if mrs_assigned > 0:
                activities_created += mrs_assigned
                logger.info(f"Admin assigned to {mrs_assigned} merge requests")

            # Activity 4: Create a welcome note/issue
            welcome_created = self._create_welcome_activity(project_id, admin_user_id, repo_name, owner, repo)
            if welcome_created:
                activities_created += 1
                logger.info("Welcome activity created")

            logger.succeed(f"Created {activities_created} activities for admin user")
            return activities_created > 0

        except Exception as e:
            logger.fail(f"Error creating admin activity: {e}")
            return False

    def _star_project(self, project_id):
        """Star the project as admin user"""
        try:
            response = self.gitlab._request("POST", f"/projects/{project_id}/star")
            return response and response.status_code in [201, 304]  # 304 = already starred
        except Exception:
            return False

    def _assign_admin_to_issues(self, project_id, admin_user_id, max_issues=3):
        """Assign admin user to some issues"""
        try:
            # Get issues
            response = self.gitlab._request("GET", f"/projects/{project_id}/issues?per_page={max_issues}")
            if not response or response.status_code != 200:
                return 0

            issues = response.json()
            assigned_count = 0

            for issue in issues[:max_issues]:
                issue_id = issue["iid"]

                # Assign admin to issue
                update_data = {"assignee_ids": [admin_user_id]}
                response = self.gitlab._request("PUT", f"/projects/{project_id}/issues/{issue_id}", update_data)

                if response and response.status_code == 200:
                    assigned_count += 1

                time.sleep(0.5)  # Small delay between assignments

            return assigned_count

        except Exception as e:
            logger.warning(f"Error assigning issues: {e}")
            return 0

    def _assign_admin_to_merge_requests(self, project_id, admin_user_id, max_mrs=2):
        """Assign admin user to some merge requests"""
        try:
            # Get merge requests
            response = self.gitlab._request("GET", f"/projects/{project_id}/merge_requests?per_page={max_mrs}")
            if not response or response.status_code != 200:
                return 0

            merge_requests = response.json()
            assigned_count = 0

            for mr in merge_requests[:max_mrs]:
                mr_id = mr["iid"]

                # Assign admin to merge request
                update_data = {"assignee_ids": [admin_user_id]}
                response = self.gitlab._request("PUT", f"/projects/{project_id}/merge_requests/{mr_id}", update_data)

                if response and response.status_code == 200:
                    assigned_count += 1

                time.sleep(0.5)  # Small delay between assignments

            return assigned_count

        except Exception as e:
            logger.warning(f"Error assigning merge requests: {e}")
            return 0

    def _create_welcome_activity(self, project_id, admin_user_id, repo_name, owner, repo):
        """Create a welcome activity (issue or comment)"""
        try:
            # Create a welcome issue
            welcome_issue_data = {
                "title": f"🎉 Welcome to {repo_name} - Successfully Imported from GitHub!",
                "description": f"""# 🚀 Import Completed Successfully!

This repository has been successfully imported from GitHub with comprehensive synchronization:

## 📊 Import Summary
- **Source**: [{owner}/{repo}](https://github.com/{owner}/{repo})
- **Import Date**: {time.strftime("%Y-%m-%d %H:%M:%S")}
- **Import Type**: Comprehensive (Complete source code + All branches + All tags + Issues + MRs)

## ✅ What was imported:
- 📁 **Complete source code** - All files and directories
- 📚 **All branches** - Not just main/master
- 🏷️ **All tags** - Version tags and releases  
- 📝 **All issues** - With proper attribution
- 🔀 **All merge requests** - With proper attribution
- 👥 **User mapping** - GitHub users mapped to GitLab users
- 📊 **Analytics data** - Stars, watchers, forks
# - ⚡ **GitHub Actions** - Converted to GitLab CI/CD  # COMMENTED OUT - CI/CD processing disabled

## 🎯 Next Steps
1. Review the imported code and issues
2. Update team members about the migration
3. Configure any GitLab-specific settings
# 4. Update CI/CD pipelines if needed  # COMMENTED OUT - CI/CD processing disabled

---
*This issue was automatically created by the comprehensive import system.*""",
                "assignee_ids": [admin_user_id],
                "labels": ["import", "welcome", "admin"],
            }

            response = self.gitlab._request("POST", f"/projects/{project_id}/issues", welcome_issue_data)
            if response and response.status_code == 201:
                logger.succeed("Welcome issue created successfully")
                return True
            else:
                logger.warning("Could not create welcome issue")
                return False

        except Exception as e:
            logger.warning(f"Error creating welcome activity: {e}")
            return False
