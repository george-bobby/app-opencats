"""API utilities for OpenCATS - HTTP form submissions and session management."""

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import aiohttp
from tenacity import retry, stop_after_attempt, wait_fixed

from apps.opencats.config.settings import settings
from common.logger import logger


class OpenCATSAPIUtils:
    """API utilities for OpenCATS form submissions and session management."""

    def __init__(self):
        self.base_url = settings.OPENCATS_API_URL
        self.session = None
        self.cookies = None

    async def __aenter__(self):
        logger.info("Initializing OpenCATS API utilities...")
        self.session = aiohttp.ClientSession()
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def authenticate(self) -> bool:
        """Authenticate with OpenCATS and maintain session."""
        try:
            login_url = urljoin(self.base_url, "/index.php?m=login&a=attemptLogin")
            login_data = {
                "username": settings.OPENCATS_ADMIN_EMAIL,
                "password": settings.OPENCATS_ADMIN_PASSWORD,
            }

            if settings.OPENCATS_SITE_NAME:
                login_data["siteName"] = settings.OPENCATS_SITE_NAME

            async with self.session.post(login_url, data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, allow_redirects=True) as response:
                if response.status == 200:
                    # Store cookies for subsequent requests
                    self.cookies = response.cookies
                    logger.info("✅ Successfully authenticated with OpenCATS")
                    return True
                else:
                    logger.error(f"❌ Authentication failed with status: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Authentication error: {e!s}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def submit_form(self, endpoint: str, form_data: dict[str, Any]) -> dict[str, Any] | None:
        """Submit a form to OpenCATS and return response data."""
        try:
            url = urljoin(self.base_url, endpoint)

            # Ensure postback is included
            if "postback" not in form_data:
                form_data["postback"] = "postback"

            async with self.session.post(url, data=form_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, cookies=self.cookies, allow_redirects=True) as response:
                response_text = await response.text()

                result = {"status_code": response.status, "url": str(response.url), "content": response_text, "entity_id": None}

                # Try to extract entity ID from redirect URL
                if response.status in [200, 302]:
                    entity_id = self._extract_entity_id_from_url(str(response.url))
                    if not entity_id:
                        entity_id = self._extract_entity_id_from_content(response_text)
                    result["entity_id"] = entity_id

                return result

        except Exception as e:
            logger.error(f"❌ Form submission error: {e!s}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def ajax_request(self, function: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Submit an AJAX request to OpenCATS."""
        try:
            url = urljoin(self.base_url, "/ajax.php")

            # Add function parameter
            ajax_data = {"f": function, **data}

            async with self.session.post(url, data=ajax_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, cookies=self.cookies) as response:
                response_text = await response.text()

                return {"status_code": response.status, "content": response_text}

        except Exception as e:
            logger.error(f"❌ AJAX request error: {e!s}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_request(self, url_path: str) -> dict[str, Any] | None:
        """Make a GET request to OpenCATS."""
        try:
            url = urljoin(self.base_url, url_path)

            async with self.session.get(url, cookies=self.cookies, allow_redirects=True) as response:
                response_text = await response.text()

                return {"status_code": response.status, "url": str(response.url), "content": response_text}

        except Exception as e:
            logger.error(f"❌ GET request error: {e!s}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def update_pipeline_status(self, candidate_id: int, joborder_id: int, status_id: int) -> bool:
        """Update the pipeline status for a candidate-job order association."""
        try:
            # Use AJAX to update pipeline status
            # OpenCATS typically uses candidates:updatePipelineStatus or similar
            ajax_data = {
                "candidateID": str(candidate_id),
                "jobOrderID": str(joborder_id),
                "statusID": str(status_id),
            }

            result = await self.ajax_request("joborders:updatePipelineStatus", ajax_data)

            if result and result.get("status_code") == 200:
                return True
            else:
                # Try alternative method using form submission
                url_path = f"/index.php?m=candidates&a=updatePipelineStatus"
                form_data = {
                    "candidateID": str(candidate_id),
                    "jobOrderID": str(joborder_id),
                    "statusID": str(status_id),
                    "postback": "postback"
                }
                
                result = await self.submit_form(url_path, form_data)
                return result is not None and result.get("status_code") == 200

        except Exception as e:
            logger.error(f"❌ Error updating pipeline status: {e!s}")
            return False


    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_latest_entity_id(self, module: str, entity_type: str) -> int | None:
        """Get the latest entity ID from a module listing page."""
        try:
            url = urljoin(self.base_url, f"/index.php?m={module}")

            async with self.session.get(url, cookies=self.cookies) as response:
                if response.status == 200:
                    content = await response.text()
                    return self._extract_latest_entity_id(content, entity_type)

        except Exception as e:
            logger.error(f"❌ Error getting latest entity ID: {e!s}")

        return None

    def _extract_entity_id_from_url(self, url: str) -> int | None:
        """Extract entity ID from URL parameters."""
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            # Common ID parameter patterns
            id_patterns = ["companyID", "contactID", "candidateID", "jobOrderID", "savedListID", "eventID", "calendarEventID"]

            for pattern in id_patterns:
                if pattern in query_params:
                    return int(query_params[pattern][0])

        except (ValueError, IndexError, KeyError):
            pass

        return None

    def _extract_entity_id_from_content(self, content: str) -> int | None:
        """Extract entity ID from HTML content."""
        try:
            # Look for ID patterns in the HTML content
            id_patterns = [
                r"companyID[=:](\d+)",
                r"contactID[=:](\d+)",
                r"candidateID[=:](\d+)",
                r"jobOrderID[=:](\d+)",
                r"savedListID[=:](\d+)",
                r"eventID[=:](\d+)",
                r"calendarEventID[=:](\d+)",
            ]

            for pattern in id_patterns:
                match = re.search(pattern, content)
                if match:
                    return int(match.group(1))

        except (ValueError, AttributeError):
            pass

        return None

    def _extract_latest_entity_id(self, content: str, entity_type: str) -> int | None:
        """Extract the latest entity ID from listing page content."""
        try:
            # Map entity types to ID patterns
            pattern_map = {
                "company": r"companyID=(\d+)",
                "contact": r"contactID=(\d+)",
                "candidate": r"candidateID=(\d+)",
                "joborder": r"jobOrderID=(\d+)",
                "event": r"eventID=(\d+)",
                "list": r"savedListID=(\d+)",
            }

            pattern = pattern_map.get(entity_type)
            if not pattern:
                return None

            matches = re.findall(pattern, content)
            if matches:
                # Return the highest ID (most recent)
                return max(int(match) for match in matches)

        except (ValueError, TypeError):
            pass

        return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_all_items(self, endpoint) -> list[dict[str, Any]]:
        """Get all items from a specific endpoint using the listing pages."""
        try:
            # Map endpoint to listing URL and ID pattern
            url_map = {
                "candidates": "/index.php?m=candidates&a=listByView&view=1",
                "companies": "/index.php?m=companies",
                "contacts": "/index.php?m=contacts",
                "joborders": "/index.php?m=joborders",
            }
            
            # Extract endpoint name from enum
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            url_path = url_map.get(endpoint_name)
            
            if not url_path:
                logger.warning(f"⚠️ No URL mapped for endpoint: {endpoint_name}")
                return []
            
            url = urljoin(self.base_url, url_path)
            
            # Get the listing page
            async with self.session.get(url, cookies=self.cookies) as response:
                if response.status == 200:
                    content = await response.text()
                    items = self._extract_items_from_listing(content, endpoint_name)
                    
                    # For contacts, we need more details - fetch each one
                    if endpoint_name == "contacts" and items:
                        detailed_items = []
                        for item in items:
                            contact_id = item.get("contactID")
                            if contact_id:
                                detailed_item = await self.get_item_details(endpoint_name, contact_id)
                                if detailed_item:
                                    # Merge the companyID from listing with detailed data
                                    if "companyID" in item:
                                        detailed_item["companyID"] = item["companyID"]
                                    detailed_items.append(detailed_item)
                        items = detailed_items
                    
                    logger.info(f"✅ Retrieved {len(items)} {endpoint_name}")
                    return items
                else:
                    logger.warning(f"⚠️ Failed to retrieve {endpoint_name}: status {response.status}")
                    return []
                
        except Exception as e:
            logger.error(f"❌ Error retrieving all {endpoint_name}: {e!s}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_item_details(self, endpoint_name: str, item_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific item."""
        try:
            # Map endpoint to view URL pattern
            url_map = {
                "candidates": f"/index.php?m=candidates&a=show&candidateID={item_id}",
                "companies": f"/index.php?m=companies&a=show&companyID={item_id}",
                "contacts": f"/index.php?m=contacts&a=show&contactID={item_id}",
                "joborders": f"/index.php?m=joborders&a=show&jobOrderID={item_id}",
            }
            
            url_path = url_map.get(endpoint_name)
            
            if not url_path:
                logger.warning(f"⚠️ No view URL pattern mapped for endpoint: {endpoint_name}")
                return None
                
            url = urljoin(self.base_url, url_path)
            
            async with self.session.get(url, cookies=self.cookies) as response:
                if response.status == 200:
                    content = await response.text()
                    item = self._extract_item_details(content, endpoint_name, item_id)
                    return item
                else:
                    logger.warning(f"⚠️ Failed to get {endpoint_name} ID {item_id}: status {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting {endpoint_name} ID {item_id}: {e!s}")
            return None

    def _extract_item_details(self, content: str, endpoint_name: str, item_id: int) -> dict[str, Any] | None:
        """Extract detailed item information from view page."""
        try:
            if endpoint_name == "contacts":
                # Extract contact details from the view page
                item = {"contactID": item_id}
                
                # Extract first name and last name
                fname_match = re.search(r'name="firstName"[^>]*value="([^"]*)"', content)
                lname_match = re.search(r'name="lastName"[^>]*value="([^"]*)"', content)
                
                if fname_match:
                    item["firstName"] = fname_match.group(1)
                if lname_match:
                    item["lastName"] = lname_match.group(1)
                
                # Extract company ID
                company_match = re.search(r'companyID[=:](\d+)', content)
                if company_match:
                    item["companyID"] = int(company_match.group(1))
                
                # Extract reportsTo value
                reports_match = re.search(r'name="reportsTo"[^>]*value="([^"]*)"', content)
                if reports_match and reports_match.group(1):
                    item["reportsTo"] = int(reports_match.group(1))
                    
                return item
                
            elif endpoint_name == "companies":
                item = {"companyID": item_id}
                
                # Extract company name
                name_match = re.search(r'name="name"[^>]*value="([^"]*)"', content)
                if name_match:
                    item["name"] = name_match.group(1)
                
                # Extract billing contact
                billing_match = re.search(r'name="billingContact"[^>]*value="([^"]*)"', content)
                if billing_match and billing_match.group(1):
                    item["billingContact"] = int(billing_match.group(1))
                    
                return item
                
            elif endpoint_name == "candidates":
                item = {"candidateID": item_id}
                
                fname_match = re.search(r'name="firstName"[^>]*value="([^"]*)"', content)
                lname_match = re.search(r'name="lastName"[^>]*value="([^"]*)"', content)
                
                if fname_match:
                    item["firstName"] = fname_match.group(1)
                if lname_match:
                    item["lastName"] = lname_match.group(1)
                    
                return item
                
            elif endpoint_name == "joborders":
                item = {"jobOrderID": item_id}
                
                title_match = re.search(r'name="title"[^>]*value="([^"]*)"', content)
                if title_match:
                    item["title"] = title_match.group(1)
                    
                return item
                
        except Exception as e:
            logger.error(f"❌ Error extracting {endpoint_name} details: {e!s}")
            
        return None


    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_item(self, endpoint, item_id: int) -> dict[str, Any] | None:
        """Get a specific item by ID."""
        try:
            # Map endpoint to view URL pattern
            url_map = {
                "candidates": f"/index.php?m=candidates&a=show&candidateID={item_id}",
                "companies": f"/index.php?m=companies&a=show&companyID={item_id}",
                "contacts": f"/index.php?m=contacts&a=show&contactID={item_id}",
                "joborders": f"/index.php?m=joborders&a=show&jobOrderID={item_id}",
            }
            
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            url_path = url_map.get(endpoint_name)
            
            if not url_path:
                logger.warning(f"⚠️ No URL pattern mapped for endpoint: {endpoint_name}")
                return None
                
            url = urljoin(self.base_url, url_path)
            
            async with self.session.get(url, cookies=self.cookies) as response:
                if response.status == 200:
                    content = await response.text()
                    item = self._extract_item_from_view(content, endpoint_name, item_id)
                    return item
                else:
                    logger.warning(f"⚠️ Failed to get {endpoint_name} ID {item_id}: status {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error getting {endpoint_name} ID {item_id}: {e!s}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def update_item(self, endpoint, item_id: int, update_data: dict[str, Any]) -> bool:
        """Update an item using form submission."""
        try:
            # Map endpoint to edit URL pattern and form data
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            
            # Handle special cases where endpoint names don't match the URL mapping
            if endpoint_name == "companies_add":
                endpoint_name = "companies"
            elif endpoint_name == "contacts_add":
                endpoint_name = "contacts"
            elif endpoint_name == "candidates_add":
                endpoint_name = "candidates"
            elif endpoint_name == "joborders_add":
                endpoint_name = "joborders"
            
            url_map = {
                "candidates": f"/index.php?m=candidates&a=edit&candidateID={item_id}",
                "companies": f"/index.php?m=companies&a=edit&companyID={item_id}", 
                "contacts": f"/index.php?m=contacts&a=edit&contactID={item_id}",
                "joborders": f"/index.php?m=joborders&a=edit&jobOrderID={item_id}",
            }
            
            url_path = url_map.get(endpoint_name)
            
            if not url_path:
                logger.warning(f"⚠️ No update URL pattern mapped for endpoint: {endpoint_name}")
                return False
                
            # Prepare form data with ID and updates
            form_data = {
                f"{endpoint_name[:-1]}ID": item_id,  # Remove 's' from endpoint name
                **update_data
            }
            
            result = await self.submit_form(url_path, form_data)
            
            if result and result.get("status_code") == 200:
                logger.info(f"✅ Updated {endpoint_name} ID {item_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to update {endpoint_name} ID {item_id}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error updating {endpoint_name} ID {item_id}: {e!s}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def delete_item(self, endpoint, item_id: int) -> bool:
        """Delete an item using AJAX request."""
        try:
            # Map endpoint to AJAX delete function
            function_map = {
                "candidates": "candidates:delete",
                "companies": "companies:delete",
                "contacts": "contacts:delete", 
                "joborders": "joborders:delete",
            }
            
            endpoint_name = endpoint.name.lower() if hasattr(endpoint, 'name') else str(endpoint).lower()
            function = function_map.get(endpoint_name)
            
            if not function:
                logger.warning(f"⚠️ No delete function mapped for endpoint: {endpoint_name}")
                return False
                
            # Prepare delete data
            delete_data = {
                f"{endpoint_name[:-1]}ID": item_id  # Remove 's' from endpoint name
            }
            
            result = await self.ajax_request(function, delete_data)
            
            if result and result.get("status_code") == 200:
                logger.info(f"✅ Deleted {endpoint_name} ID {item_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to delete {endpoint_name} ID {item_id}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting {endpoint_name} ID {item_id}: {e!s}")
            return False

    def _extract_items_from_listing(self, content: str, endpoint_name: str) -> list[dict[str, Any]]:
        """Extract items from listing page HTML content."""
        items = []
        try:
            # Parse HTML to extract items based on ID patterns in links
            # Look for various ID patterns in hrefs and extract surrounding data
            
            if endpoint_name == "candidates":
                # Pattern: candidateID=XXX
                # Look for all links with candidateID parameter
                pattern = r'candidateID=(\d+)'
                id_matches = re.findall(pattern, content)
                
                # Remove duplicates and create basic items
                seen_ids = set()
                for candidate_id in id_matches:
                    if candidate_id not in seen_ids:
                        seen_ids.add(candidate_id)
                        items.append({
                            "candidateID": int(candidate_id)
                        })
                        
            elif endpoint_name == "companies":
                # Pattern: companyID=XXX
                pattern = r'companyID=(\d+)'
                id_matches = re.findall(pattern, content)
                
                seen_ids = set()
                for company_id in id_matches:
                    if company_id not in seen_ids:
                        seen_ids.add(company_id)
                        items.append({
                            "companyID": int(company_id)
                        })
                        
            elif endpoint_name == "contacts":
                # Pattern: contactID=XXX  
                # Also extract companyID for contacts to properly map relationships
                # Look for patterns like: contactID=X&...&companyID=Y
                pattern = r'contactID=(\d+)[^"]*?companyID=(\d+)'
                matches = re.findall(pattern, content)
                
                seen_ids = set()
                for contact_id, company_id in matches:
                    if contact_id not in seen_ids:
                        seen_ids.add(contact_id)
                        items.append({
                            "contactID": int(contact_id),
                            "companyID": int(company_id)
                        })
                
                # Also try simpler pattern if the above doesn't work
                if not items:
                    simple_pattern = r'contactID=(\d+)'
                    id_matches = re.findall(simple_pattern, content)
                    seen_ids = set()
                    for contact_id in id_matches:
                        if contact_id not in seen_ids:
                            seen_ids.add(contact_id)
                            items.append({
                                "contactID": int(contact_id)
                            })
                        
            elif endpoint_name == "joborders":
                # Pattern: jobOrderID=XXX
                pattern = r'jobOrderID=(\d+)'
                id_matches = re.findall(pattern, content)
                
                seen_ids = set()
                for job_id in id_matches:
                    if job_id not in seen_ids:
                        seen_ids.add(job_id)
                        items.append({
                            "jobOrderID": int(job_id)
                        })
                        
        except Exception as e:
            logger.error(f"❌ Error parsing {endpoint_name} listing: {e!s}")
            
        return items

    def _extract_item_from_view(self, content: str, endpoint_name: str, item_id: int) -> dict[str, Any] | None:
        """Extract item details from view page HTML content."""
        try:
            # Simplified extraction - in a real implementation, use proper HTML parsing
            item = {f"{endpoint_name[:-1]}ID": item_id}
            
            if endpoint_name == "candidates":
                # Extract candidate details
                name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', content)
                if name_match:
                    names = name_match.group(1).split()
                    item.update({
                        "firstName": names[0] if names else "",
                        "lastName": " ".join(names[1:]) if len(names) > 1 else ""
                    })
                    
            elif endpoint_name == "companies":
                # Extract company details
                name_match = re.search(r'<h2[^>]*>([^<]+)</h2>', content)
                if name_match:
                    item["name"] = name_match.group(1).strip()
                    
            # Add more extraction logic for other endpoints as needed
            
            return item
            
        except Exception as e:
            logger.error(f"❌ Error parsing {endpoint_name} view: {e!s}")
            return None
