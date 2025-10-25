import json
from typing import Any

import aiohttp

from common.logger import logger


async def make_anthropic_request(
    prompt: str,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> dict[str, Any] | None:
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is required")
        return None

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    try:
        # Increased timeout for large requests
        timeout = aiohttp.ClientTimeout(total=180)  # 3 minutes instead of 60 seconds

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=timeout,
            ) as response,
        ):
            response_data = await response.json()

            if response.status == 200:
                return response_data
            else:
                # Return error details instead of None so caller can handle it
                logger.error(f"Anthropic API request failed: {response.status}")
                logger.debug(f"Error response: {response_data}")

                # Return the error in a structured way
                return {
                    "error": {
                        "type": response_data.get("error", {}).get("type", "api_error"),
                        "message": response_data.get("error", {}).get("message", f"HTTP {response.status}"),
                    }
                }

    except aiohttp.ClientError as e:
        logger.error(f"Anthropic API network error: {e!s}")
        return {
            "error": {
                "type": "network_error",
                "message": str(e),
            }
        }
    except Exception as e:
        logger.error(f"Anthropic API request failed: {e!s}")
        return {
            "error": {
                "type": "unknown_error",
                "message": str(e),
            }
        }


def parse_anthropic_response(response_data: dict[str, Any]) -> list[dict] | None:
    try:
        if "content" not in response_data:
            logger.error("No content in Anthropic response")
            return None

        content = response_data["content"]
        if not content or not isinstance(content, list):
            logger.error("Invalid content format in Anthropic response")
            return None

        text_content = content[0].get("text", "")
        if not text_content:
            logger.error("No text content in Anthropic response")
            return None

        # Find JSON array boundaries
        json_start = text_content.find("[")
        if json_start == -1:
            logger.error("No JSON array found in Anthropic response")
            return None
        
        # Find the matching closing bracket for the JSON array
        bracket_count = 0
        json_end = -1
        in_string = False
        escape_next = False
        
        for i in range(json_start, len(text_content)):
            char = text_content[i]
            
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_end = i + 1
                        break
        
        if json_end == -1:
            # Fallback to simple rfind if parsing fails
            json_end = text_content.rfind("]") + 1
        
        if json_end == 0:
            logger.error("No closing bracket found for JSON array")
            return None

        json_str = text_content[json_start:json_end]
        
        # Clean up common issues
        json_str = json_str.strip()
        
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Anthropic response: {e}")
        # Log a snippet of the problematic JSON for debugging
        if 'json_str' in locals():
            snippet = json_str[:200] + "..." if len(json_str) > 200 else json_str
            logger.debug(f"JSON snippet: {snippet}")
        return None
    except Exception as e:
        logger.error(f"Error parsing Anthropic response: {e}")
        return None


def validate_anthropic_config(api_key: str | None = None) -> None:
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required. Please set it in your environment or .env file.")

    logger.debug("Anthropic API configuration validated")
