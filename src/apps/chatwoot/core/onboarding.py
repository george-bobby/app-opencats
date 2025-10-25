import re

import aiohttp

from apps.chatwoot.config.settings import settings
from common.logger import logger


async def setup_onboarding(url_override=None):
    chatwoot_url = url_override or settings.CHATWOOT_URL
    print(f"Connecting to Chatwoot URL: {chatwoot_url}")

    # Browser-like headers to avoid 406 Not Acceptable
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/117.0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    async with aiohttp.ClientSession() as session:  # noqa: SIM117
        # First make a GET request to obtain cookies and authenticity token
        async with session.get(f"{chatwoot_url}/installation/onboarding", headers=headers) as get_response:
            logger.info(f"GET Response status: {get_response.status}")

            if get_response.status == 406:
                logger.error("Server rejected our request with 406 Not Acceptable. Check content negotiation headers.")
                return "Error: Server rejected request with 406 Not Acceptable"

            cookies = get_response.cookies
            html_content = await get_response.text()

            logger.debug(f"Response headers: {get_response.headers}")
            logger.debug(f"Cookies from GET request: {cookies}")

            # Extract authenticity token from HTML
            authenticity_token = None
            token_match = re.search(r'name="authenticity_token" value="([^"]+)"', html_content)
            if token_match:
                authenticity_token = token_match.group(1)
                logger.info(f"Extracted authenticity token: {authenticity_token}")
            else:
                logger.error("Could not find authenticity token in the response")

                # Try alternative patterns
                alt_patterns = [
                    r'name="csrf-token" content="([^"]+)"',
                    r'input[^>]+name="authenticity_token"[^>]+value="([^"]+)"',
                    r'data-csrf="([^"]+)"',
                ]

                for pattern in alt_patterns:
                    alt_match = re.search(pattern, html_content)
                    if alt_match:
                        authenticity_token = alt_match.group(1)
                        logger.info(f"Token: {authenticity_token}")
                        break

            # Now make the POST request with the obtained cookies and token
            post_headers = headers.copy()
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"

            async with session.post(
                f"{chatwoot_url}/installation/onboarding",
                headers=post_headers,
                cookies=cookies,
                data={
                    "authenticity_token": authenticity_token,
                    "user[name]": "Johny Appleseed",
                    "user[company]": settings.COMPANY_NAME,
                    "user[email]": settings.CHATWOOT_ADMIN_EMAIL,
                    "user[password]": settings.CHATWOOT_ADMIN_PASSWORD,
                },
            ) as post_response:
                post_content = await post_response.text()
                return post_content
