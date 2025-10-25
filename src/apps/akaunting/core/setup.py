import asyncio
import re

import aiohttp

from apps.akaunting.config.settings import settings
from common.logger import logger


async def extract_csrf_token(html):
    match = re.search(r'"csrfToken":"([^"]+)"', html)
    if match:
        return match.group(1)
    return None


async def setup_database(session, url, token):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": settings.API_URL,
        "Referer": f"{settings.API_URL}/install/database",
        "X-CSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
    }

    data = aiohttp.FormData()
    data.add_field("_token", token)
    data.add_field("_method", "POST")
    data.add_field("hostname", settings.AKAUNTING_DB_HOST)
    data.add_field("username", settings.AKAUNTING_DB_USER)
    data.add_field("password", settings.AKAUNTING_DB_PASSWORD)
    data.add_field("database", settings.AKAUNTING_DB)

    async with session.post(url, headers=headers, data=data) as response:
        if response.status == 200:
            logger.info("Successfully set up Akaunting database")
        else:
            logger.error(f"Failed to set up Akaunting database. Status: {response.status}. Retrying...")

        return response.status == 200


async def setup_akaunting():
    async with aiohttp.ClientSession() as session:
        # Step 1: GET /install/language and extract CSRF token
        url = f"{settings.API_URL}/install/language"
        async with session.get(url) as response:
            html = await response.text()
            token = await extract_csrf_token(html)
            if not token:
                logger.error("CSRF Token not found in /install/language HTML response")

        # Step 2: POST to /install/language
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": settings.API_URL,
            "Referer": f"{settings.API_URL}/install/language",
            "X-CSRF-TOKEN": token,
        }
        data = aiohttp.FormData()
        data.add_field("_token", token)
        data.add_field("_method", "POST")
        data.add_field("lang", "en-US")
        async with session.post(url, headers=headers, data=data) as response:
            if response.status == 200:
                logger.info("Successfully set up Akaunting language")
            else:
                logger.error(f"Failed to set up Akaunting language. Status: {response.status}")

        # Step 3: GET /install/database and extract CSRF token
        url = f"{settings.API_URL}/install/database"
        async with session.get(url) as response:
            html = await response.text()
            token = await extract_csrf_token(html)
            if not token:
                logger.error("CSRF Token not found in /install/database HTML response")
                return

        # Step 4: First attempt to set up database
        await asyncio.sleep(10)
        success = await setup_database(session, url, token)

        # Setting up the database only work on the second attempt
        if not success:
            await asyncio.sleep(10)
            await setup_database(session, url, token)

        # Step 5: GET /install/settings and extract CSRF token
        url = f"{settings.API_URL}/install/settings"
        async with session.get(url) as response:
            html = await response.text()
            token = await extract_csrf_token(html)
            if not token:
                logger.error("CSRF Token not found in /install/settings HTML response")

        # Step 6: POST to /install/settings
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": settings.API_URL,
            "Referer": f"{settings.API_URL}/install/settings",
            "X-CSRF-TOKEN": token,
            "X-Requested-With": "XMLHttpRequest",
        }
        data = aiohttp.FormData()
        data.add_field("_token", token)
        data.add_field("_method", "POST")
        data.add_field("company_name", settings.AKAUNTING_COMPANY_NAME)
        data.add_field("company_email", settings.ADMIN_USERNAME)
        data.add_field("user_email", settings.ADMIN_USERNAME)
        data.add_field("user_password", settings.ADMIN_PASSWORD)
        async with session.post(url, headers=headers, data=data) as response:
            if response.status == 200:
                logger.info("Successfully set up Akaunting settings")
            else:
                logger.error(f"Failed to set up Akaunting settings. Status: {response.status}")

        # Step 7: POST to /wizard/companies
        await asyncio.sleep(5)  # Give the system time to process previous steps

        # Create a new session that preserves cookies
        jar = aiohttp.CookieJar(unsafe=True)  # Allow cookies from non-secure sources
        async with aiohttp.ClientSession(cookie_jar=jar) as auth_session:
            # First get the login page to obtain CSRF token
            login_url = f"{settings.API_URL}/auth/login"
            async with auth_session.get(login_url) as response:
                html = await response.text()
                login_token = await extract_csrf_token(html)
                if not login_token:
                    logger.error("CSRF token not found in login page")
                    return

                logger.info(f"Got login CSRF token: {login_token}")

            # Submit login form
            login_headers = {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-TOKEN": login_token,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": login_url,
            }

            login_data = {
                "email": settings.ADMIN_USERNAME,
                "password": settings.ADMIN_PASSWORD,
                "_token": login_token,
                "_remember": "1",
            }

            async with auth_session.post(login_url, headers=login_headers, data=login_data) as response:
                login_response = await response.text()
                logger.info(f"Login response status: {response.status}")
                logger.info(f"Login response: {login_response}")

                if response.status != 200:
                    logger.error("Login failed")
                    return

            # Now get the wizard page with authenticated session
            wizard_url = f"{settings.API_URL}/1/wizard"
            async with auth_session.get(wizard_url) as response:
                html = await response.text()
                logger.info(f"Wizard page status: {response.status}")

                token = await extract_csrf_token(html)
                if not token:
                    logger.error("CSRF Token not found in wizard page HTML response")
                    return

                # Log all cookies for debugging
                cookies = auth_session.cookie_jar.filter_cookies(response.url)
                # logger.info("All cookies:")
                # for name, cookie in cookies.items():
                #     logger.info(f"Cookie {name}: {cookie.value}")

                # Extract XSRF token from cookies
                xsrf_token = None
                for name, cookie in cookies.items():
                    if name == "XSRF-TOKEN":
                        xsrf_token = cookie.value
                        break

                if not xsrf_token:
                    logger.error("XSRF-TOKEN cookie not found")
                    return

                logger.info(f"Got XSRF token: {xsrf_token}")

            # Now make the wizard/companies request
            url = f"{settings.API_URL}/1/wizard/companies"

            boundary = "----WebKitFormBoundarymRDMA7uBRSRCissa"
            headers = {
                "Accept": "application/json, text/plain, */*",
                "X-CSRF-TOKEN": token,
                "X-XSRF-TOKEN": xsrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{settings.API_URL}/1/wizard",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }

            # Use raw form data matching the example format
            wizard_raw_data = f"""------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="api_key"

{settings.AKAUNTING_API_KEY}
------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="tax_number"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="financial_start"

01-01
------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="address"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="country"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="api_key"

{settings.AKAUNTING_API_KEY}
------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="tax_number"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="financial_start"

01-01
------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="address"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="country"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="logo"


------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="_prefix"

company
------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="_token"

{token}
------WebKitFormBoundarymRDMA7uBRSRCissa
Content-Disposition: form-data; name="_method"

POST
------WebKitFormBoundarymRDMA7uBRSRCissa--"""

            logger.info(f"Sending request to {url} with headers: {headers}")

            async with auth_session.post(url, headers=headers, data=wizard_raw_data) as response:
                response_text = await response.text()
                logger.info(f"Response: {response_text}")
                if response.status == 200:
                    logger.info("Successfully set up Akaunting company wizard")
                else:
                    logger.error(f"Failed to set up Akaunting company wizard. Status: {response.status}. Response: {response_text}")
