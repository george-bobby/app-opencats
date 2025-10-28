import json
import re
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
                # Handle API errors properly
                error_type = response_data.get("error", {}).get("type", "api_error")
                error_message = response_data.get("error", {}).get("message", f"HTTP {response.status}")
                
                logger.error(f"✖ Anthropic API request failed: {response.status}")
                logger.debug(f"🐛 Error response: {response_data}")

                # Return None for errors to stop processing
                return None

    except aiohttp.ClientError as e:
        logger.error(f"✖ Anthropic API network error: {e!s}")
        return None
    except Exception as e:
        logger.error(f"✖ Anthropic API request failed: {e!s}")
        return None


def parse_anthropic_response(response_data: dict[str, Any]) -> list[dict] | None:
    try:
        if "content" not in response_data:
            logger.error("✖ No content in Anthropic response")
            return None

        content = response_data["content"]
        if not content or not isinstance(content, list):
            logger.error("✖ Invalid content format in Anthropic response")
            return None

        text_content = content[0].get("text", "")
        if not text_content:
            logger.error("✖ No text content in Anthropic response")
            return None

        # Find JSON array boundaries
        json_start = text_content.find("[")
        if json_start == -1:
            logger.error("✖ No JSON array found in Anthropic response")
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
            # Fallback: look for the last complete bracket
            potential_ends = []
            bracket_count = 0
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
                            potential_ends.append(i + 1)
            
            if potential_ends:
                json_end = potential_ends[-1]
            else:
                # Last resort: find the last ] in the text
                last_bracket = text_content.rfind("]")
                if last_bracket > json_start:
                    json_end = last_bracket + 1
                else:
                    json_end = -1
        
        if json_end == -1 or json_end <= json_start:
            logger.error("✖ No valid JSON array ending found")
            logger.debug(f"🐛 JSON extraction failed: json_start={json_start}, json_end={json_end}")
            # Log a snippet to help with debugging
            snippet = text_content[json_start:json_start+200] + "..." if len(text_content) > json_start + 200 else text_content[json_start:]
            logger.debug(f"🐛 Text snippet from json_start: {snippet}")
            return None

        json_str = text_content[json_start:json_end]
        
        # Clean up common issues and control characters
        json_str = json_str.strip()
        
        # Remove/replace common problematic control characters
        # Replace control characters except for \n, \r, and \t with spaces
        json_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', ' ', json_str)
        
        # Clean up extra whitespace that might have been introduced
        json_str = re.sub(r'\s+', ' ', json_str)
        
        # Fix common JSON issues
        # Remove trailing commas before closing brackets/braces
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Ensure strings are properly quoted (basic fix for unquoted strings)
        # This is a simple fix - more complex cases might need specialized handling
        
        try:
            # First attempt: parse as-is
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Second attempt: try to fix common issues
            logger.warning(f"⚠ Initial JSON parse failed, attempting fixes: {e}")
            
            # Try to fix incomplete JSON by removing incomplete objects at the end
            if "Expecting ',' delimiter" in str(e) or "Expecting ':' delimiter" in str(e):
                # Find the last complete object
                last_complete_brace = json_str.rfind('}')
                if last_complete_brace > 0:
                    # Try parsing up to the last complete object
                    truncated_json = json_str[:last_complete_brace + 1] + ']'
                    try:
                        logger.info("🔧 Attempting to parse truncated JSON")
                        return json.loads(truncated_json)
                    except json.JSONDecodeError:
                        pass
            
            # If all fixes fail, re-raise the original error
            raise e

    except json.JSONDecodeError as e:
        logger.error(f"✖ Failed to parse JSON from Anthropic response: {e}")
        # Log a snippet of the problematic JSON for debugging
        if 'json_str' in locals():
            snippet = json_str[:300] + "..." if len(json_str) > 300 else json_str
            logger.debug(f"🐛 JSON snippet: {snippet}")
        return None
    except Exception as e:
        logger.error(f"✖ Error parsing Anthropic response: {e}")
        return None


def validate_anthropic_config(api_key: str | None = None) -> None:
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required. Please set it in your environment or .env file.")

    logger.debug("Anthropic API configuration validated")
