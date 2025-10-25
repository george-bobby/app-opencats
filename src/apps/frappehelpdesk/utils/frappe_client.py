import asyncio
import json
from base64 import b64encode
from io import StringIO
from typing import Any
from urllib.parse import quote

import aiohttp

from apps.frappehelpdesk.config.settings import settings


class AuthError(Exception):
    pass


class FrappeError(Exception):
    pass


class NotUploadableError(FrappeError):
    def __init__(self, doctype: str):
        self.message = f"The doctype `{doctype}` is not uploadable, so you can't download the template"


class FrappeClient:
    def __init__(
        self,
        url: str = settings.API_URL,
        username: str = settings.ADMIN_USERNAME,
        password: str = settings.ADMIN_PASSWORD,
        api_key: str | None = None,
        api_secret: str | None = None,
        verify: bool = True,
    ):
        self.headers = {"Accept": "application/json"}
        self.session: aiohttp.ClientSession | None = None
        self.can_download: list[str] = []
        self.verify = verify
        self.url = url
        self.username = username
        self.password = password
        self.is_logged_in = False

        if api_key and api_secret:
            token = b64encode(f"{api_key}:{api_secret}".encode()).decode()
            self.headers["Authorization"] = f"Basic {token}"

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl=self.verify)
        self.session = aiohttp.ClientSession(headers=self.headers, connector=connector)
        try:
            await self.login(self.username, self.password)
            return self
        except Exception as e:
            # If login fails, ensure session is cleaned up
            if self.session and not self.session.closed:
                await self.session.close()
            raise e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.is_logged_in:
                await self.logout()
        except Exception:
            pass  # Ignore logout errors
        finally:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def login(self, username: str, password: str) -> dict:
        if not self.session:
            connector = aiohttp.TCPConnector(ssl=self.verify)
            self.session = aiohttp.ClientSession(headers=self.headers, connector=connector)

        headers = {
            "Content-Type": "application/json",
        }

        data = {
            "usr": username,
            "pwd": password,
        }

        max_retries = 3
        retry_delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                async with self.session.post(
                    f"{self.url}/api/method/login",
                    json=data,
                    headers=headers,
                ) as response:
                    if not response.ok:
                        if response.status == 401:
                            raise AuthError(f"Login failed: Invalid credentials for user {username}")
                        raise AuthError(f"Login failed with status code {response.status}")

                    json_response = await response.json()
                    self.can_download = []
                    self.is_logged_in = True
                    return json_response

            except (aiohttp.ClientError, AuthError) as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise AuthError(f"Login failed after {max_retries} attempts: {e!s}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

    async def logout(self) -> None:
        if self.session and self.is_logged_in:
            try:
                headers = {
                    "Accept": "application/json",
                }
                async with self.session.post(f"{self.url}/api/method/logout", json={}, headers=headers) as response:
                    if response.ok:
                        self.is_logged_in = False
            except Exception:
                pass  # Ignore logout errors

    async def close(self) -> None:
        """Explicitly close the session and cleanup resources"""
        try:
            if self.is_logged_in:
                await self.logout()
        except Exception:
            pass
        finally:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def get_list(
        self,
        doctype: str,
        fields: list[str] | None = None,
        filters: dict | None = None,
        limit_start: int = 0,
        limit_page_length: int = 0,
        order_by: str | None = None,
    ) -> dict:
        if fields is None:
            fields = ["*"]

        params = {"fields": json.dumps(fields)}
        if filters:
            params["filters"] = json.dumps(filters)
        if limit_page_length:
            params["limit_start"] = limit_start
            params["limit_page_length"] = limit_page_length
        if order_by:
            params["order_by"] = order_by

        async with self.session.get(f"{self.url}/api/resource/{doctype}", params=params) as response:
            return await self._post_process(response)

    async def insert(self, doc: dict) -> dict:
        async with self.session.post(
            f"{self.url}/api/resource/{quote(doc.get('doctype'))}",
            data={"data": json.dumps(doc)},
        ) as response:
            return await self._post_process(response)

    async def insert_many(self, docs: list[dict]) -> dict:
        return await self._post_request({"cmd": "frappe.client.insert_many", "docs": json.dumps(docs)})

    async def update(self, doc: dict) -> dict:
        url = f"{self.url}/api/resource/{quote(doc.get('doctype'))}/{quote(doc.get('name'))}"
        async with self.session.put(url, data={"data": json.dumps(doc)}) as response:
            return await self._post_process(response)

    async def bulk_update(self, docs: list[dict]) -> dict:
        return await self._post_request({"cmd": "frappe.client.bulk_update", "docs": json.dumps(docs)})

    async def delete(self, doctype: str, name: str) -> dict:
        return await self._post_request({"cmd": "frappe.client.delete", "doctype": doctype, "name": name})

    async def submit(self, doclist: dict) -> dict:
        return await self._post_request({"cmd": "frappe.client.submit", "doclist": json.dumps(doclist)})

    async def get_value(self, doctype: str, fieldname: str | None = None, filters: dict | None = None) -> dict:
        return await self._get_request(
            {
                "cmd": "frappe.client.get_value",
                "doctype": doctype,
                "fieldname": fieldname or "name",
                "filters": json.dumps(filters),
            }
        )

    async def set_value(self, doctype: str, docname: str, fieldname: str, value: Any) -> dict:
        return await self._post_request(
            {
                "cmd": "frappe.client.set_value",
                "doctype": doctype,
                "name": docname,
                "fieldname": fieldname,
                "value": value,
            }
        )

    async def cancel(self, doctype: str, name: str) -> dict:
        return await self._post_request({"cmd": "frappe.client.cancel", "doctype": doctype, "name": name})

    async def get_doc(
        self,
        doctype: str,
        name: str = "",
        filters: dict | None = None,
        fields: list[str] | None = None,
    ) -> dict:
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)

        async with self.session.get(f"{self.url}/api/resource/{doctype}/{name}", params=params) as response:
            return await self._post_process(response)

    async def rename_doc(self, doctype: str, old_name: str, new_name: str) -> dict:
        return await self._post_request(
            {
                "cmd": "frappe.client.rename_doc",
                "doctype": doctype,
                "old_name": old_name,
                "new_name": new_name,
            }
        )

    async def get_pdf(
        self,
        doctype: str,
        name: str,
        print_format: str = "Standard",
        letterhead: bool = True,
    ) -> StringIO:
        params = {
            "doctype": doctype,
            "name": name,
            "format": print_format,
            "no_letterhead": int(not letterhead),
        }
        async with self.session.get(
            f"{self.url}/api/method/frappe.templates.pages.print.download_pdf",
            params=params,
        ) as response:
            return await self._post_process_file_stream(response)

    async def get_html(
        self,
        doctype: str,
        name: str,
        print_format: str = "Standard",
        letterhead: bool = True,
    ) -> StringIO:
        params = {
            "doctype": doctype,
            "name": name,
            "format": print_format,
            "no_letterhead": int(not letterhead),
        }
        async with self.session.get(f"{self.url}/print", params=params) as response:
            return await self._post_process_file_stream(response)

    async def _load_downloadable_templates(self) -> None:
        self.can_download = await self.get_api("frappe.core.page.data_import_tool.data_import_tool.get_doctypes")

    async def get_upload_template(self, doctype: str, with_data: bool = False) -> StringIO:
        if not self.can_download:
            await self._load_downloadable_templates()

        if doctype not in self.can_download:
            raise NotUploadableError(doctype)

        params = {
            "doctype": doctype,
            "parent_doctype": doctype,
            "with_data": "Yes" if with_data else "No",
            "all_doctypes": "Yes",
        }

        async with self.session.get(
            f"{self.url}/api/method/frappe.core.page.data_import_tool.exporter.get_template",
            params=params,
        ) as response:
            return await self._post_process_file_stream(response)

    async def get_api(self, method: str, params: dict | None = None) -> dict:
        if params is None:
            params = {}
        async with self.session.get(f"{self.url}/api/method/{method}/", params=params) as response:
            return await self._post_process(response)

    async def post_api(self, method: str, params: dict | None = None) -> dict:
        if params is None:
            params = {}

        headers = {
            "Content-Type": "application/json; charset=utf-8",
        }

        async with self.session.post(f"{self.url}/api/method/{method}/", json=params, headers=headers) as response:
            return await self._post_process(response)

    async def _get_request(self, params: dict) -> dict:
        async with self.session.get(self.url, params=self._preprocess(params)) as response:
            return await self._post_process(response)

    async def _post_request(self, data: dict) -> dict:
        async with self.session.post(self.url, data=self._preprocess(data)) as response:
            return await self._post_process(response)

    def _preprocess(self, params: dict) -> dict:
        """Convert dicts, lists to json"""
        processed = params.copy()
        for key, value in processed.items():
            if isinstance(value, dict | list):
                processed[key] = json.dumps(value)
        return processed

    async def _post_process(self, response: aiohttp.ClientResponse) -> dict:
        try:
            rjson = await response.json()
        except ValueError:
            text = await response.text()
            print(text)
            raise

        if rjson and ("exc" in rjson) and rjson["exc"]:
            raise FrappeError(rjson["exc"])
        if "message" in rjson:
            return rjson["message"]
        elif "data" in rjson:
            return rjson["data"]
        return None

    async def _post_process_file_stream(self, response: aiohttp.ClientResponse) -> StringIO | None:
        if response.ok:
            output = StringIO()
            async for block in response.content.iter_chunked(1024):
                output.write(block.decode())
            return output

        try:
            rjson = await response.json()
        except ValueError:
            text = await response.text()
            print(text)
            raise

        if rjson and ("exc" in rjson) and rjson["exc"]:
            raise FrappeError(rjson["exc"])
        if "message" in rjson:
            return rjson["message"]
        elif "data" in rjson:
            return rjson["data"]
        return None
