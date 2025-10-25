import json
import re
import uuid
from typing import Any

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from common.logger import logger


class HtmlToRichContentConverter:
    def __init__(self):
        self.content = []

    def convert(self, html_text: str) -> list[dict[str, Any]]:
        """Convert HTML text to rich content format"""
        self.content = []

        # Parse HTML
        soup = BeautifulSoup(html_text, "html.parser")

        # Process each top-level element
        for element in soup.children:
            if isinstance(element, Tag):
                self._process_element(element)
            elif isinstance(element, NavigableString) and element.strip():
                # Handle loose text
                self._add_paragraph(str(element))

        # Generate response in the required format
        page_id = self._generate_id()
        return [
            {
                "description": {"content": self.content, "type": "doc"},
                "id": page_id,
                "page_id": page_id,
                "title": None,
                "updated_at": "2025-01-15T00:00:00Z",
                "variant_id": None,
            }
        ]

    def _generate_id(self) -> str:
        """Generate a unique ID similar to the format in the example"""
        return str(uuid.uuid4()).replace("-", "")[:22] + "=="

    def _process_element(self, element: Tag):
        """Process a single HTML element"""
        tag_name = element.name.lower()

        if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            self._add_heading(element)
        elif tag_name == "p":
            self._add_paragraph_element(element)
        elif tag_name == "ul":
            self._add_bullet_list(element)
        elif tag_name == "ol":
            self._add_numbered_list(element)
        elif tag_name == "blockquote":
            self._add_blockquote(element)
        elif tag_name == "img":
            self._add_image(element)
        elif tag_name == "hr":
            self.content.append({"type": "horizontalRule"})
        elif tag_name == "iframe":
            self._add_iframe(element)
        elif tag_name == "div" and self._is_youtube_embed(element):
            self._add_youtube_embed(element)
        elif tag_name == "br":
            # Handle line breaks - add empty paragraph
            self.content.append({"type": "paragraph"})
        else:
            # Check for special content like license keys
            text_content = element.get_text().strip().lower()
            if text_content in [
                "license key",
                "[license key]",
                "{{license_key}}",
                "[licensekey]",
            ]:
                self.content.append({"type": "licenseKey"})
            else:
                # For other elements, process their children
                for child in element.children:
                    if isinstance(child, Tag):
                        self._process_element(child)
                    elif isinstance(child, NavigableString) and child.strip():
                        self._add_paragraph(str(child))

    def _add_heading(self, element: Tag):
        """Add a heading element"""
        level = int(element.name[1])  # Extract number from h1, h2, etc.
        content = self._parse_inline_content(element)

        heading = {
            "attrs": {"level": level},
            "content": content,
            "type": "heading",
        }
        self.content.append(heading)

    def _add_paragraph_element(self, element: Tag):
        """Add a paragraph element from HTML p tag"""
        content = self._parse_inline_content(element)
        if content:
            paragraph = {
                "content": content,
                "type": "paragraph",
            }
            self.content.append(paragraph)
        else:
            self.content.append({"type": "paragraph"})

    def _add_paragraph(self, text: str):
        """Add a paragraph element from plain text"""
        if not text.strip():
            self.content.append({"type": "paragraph"})
            return

        paragraph = {
            "content": [{"text": text.strip(), "type": "text"}],
            "type": "paragraph",
        }
        self.content.append(paragraph)

    def _add_bullet_list(self, element: Tag):
        """Add a bullet list"""
        list_items = []

        for li in element.find_all("li", recursive=False):
            content = self._parse_inline_content(li)
            list_item = {
                "content": [
                    {
                        "content": content,
                        "type": "paragraph",
                    }
                ],
                "type": "listItem",
            }
            list_items.append(list_item)

        if list_items:
            bullet_list = {"content": list_items, "type": "bulletList"}
            self.content.append(bullet_list)

    def _add_numbered_list(self, element: Tag):
        """Add a numbered list"""
        list_items = []

        for li in element.find_all("li", recursive=False):
            content = self._parse_inline_content(li)
            list_item = {
                "content": [
                    {
                        "content": content,
                        "type": "paragraph",
                    }
                ],
                "type": "listItem",
            }
            list_items.append(list_item)

        if list_items:
            ordered_list = {"content": list_items, "type": "orderedList"}
            self.content.append(ordered_list)

    def _add_blockquote(self, element: Tag):
        """Add a blockquote"""
        content = self._parse_inline_content(element)

        blockquote = {
            "content": [
                {
                    "content": content,
                    "type": "paragraph",
                }
            ],
            "type": "blockquote",
        }
        self.content.append(blockquote)

    def _add_image(self, element: Tag):
        """Add an image element"""
        src = element.get("src", "")

        image = {"attrs": {"link": None, "src": src}, "type": "image"}
        self.content.append(image)

    def _add_iframe(self, element: Tag):
        """Add iframe as raw content"""
        src = element.get("src", "")

        # Check if it's a YouTube iframe
        if "youtube.com" in src or "youtu.be" in src:
            self._add_youtube_from_iframe(element)
        else:
            # Generic iframe
            raw_content = {"attrs": {"html": str(element), "url": src}, "type": "raw"}
            self.content.append(raw_content)

    def _is_youtube_embed(self, element: Tag) -> bool:
        """Check if element contains YouTube embed"""
        iframe = element.find("iframe")
        if iframe:
            src = iframe.get("src", "")
            return "youtube.com" in src or "youtu.be" in src or "iframe.ly" in src
        return False

    def _add_youtube_embed(self, element: Tag):
        """Add YouTube embed from div wrapper"""
        iframe = element.find("iframe")
        if iframe:
            self._add_youtube_from_iframe(iframe)

    def _add_youtube_from_iframe(self, iframe: Tag):
        """Add YouTube video from iframe element"""
        src = iframe.get("src", "")

        # Extract video ID and URL
        video_id = ""
        url = ""

        if "iframe.ly" in src:
            # Extract original URL from iframe.ly
            import urllib.parse

            parsed = urllib.parse.urlparse(src)
            query_params = urllib.parse.parse_qs(parsed.query)
            if "url" in query_params:
                original_url = urllib.parse.unquote(query_params["url"][0])
                if "youtube.com/watch?v=" in original_url:
                    video_id = original_url.split("v=")[1].split("&")[0]
                elif "youtu.be/" in original_url:
                    video_id = original_url.split("youtu.be/")[1].split("?")[0]
                url = original_url
        elif "youtube.com/embed/" in src:
            video_id = src.split("/embed/")[1].split("?")[0]
            url = f"https://www.youtube.com/watch?v={video_id}"

        if video_id:
            # Get the parent div's HTML for the full embed structure
            parent = iframe.parent
            html_content = str(parent) if parent else str(iframe)

            raw_content = {
                "attrs": {
                    "html": html_content,
                    "thumbnail": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                    "title": "YouTube Video",
                    "url": url,
                },
                "type": "raw",
            }
            self.content.append(raw_content)

    def _parse_inline_content(self, element: Tag) -> list[dict[str, Any]]:
        """Parse inline content within an element"""
        result = []

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip():
                    # Check for standalone URLs in text
                    result.extend(self._parse_text_for_urls(text))
            elif isinstance(child, Tag):
                result.extend(self._parse_inline_tag(child))

        return result if result else []

    def _parse_text_for_urls(self, text: str) -> list[dict[str, Any]]:
        """Parse text content and convert standalone URLs to links"""
        if not text.strip():
            return []

        # Pattern to match URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?\)\]\}]'

        result = []
        current_pos = 0

        for url_match in re.finditer(url_pattern, text):
            # Add text before URL
            before_text = text[current_pos : url_match.start()]
            if before_text.strip():
                result.append({"text": before_text, "type": "text"})

            # Add URL as link
            url = url_match.group()
            link_element = {
                "attrs": {"href": url},
                "content": [{"text": url, "type": "text"}],
                "type": "tiptap-link",
            }
            result.append(link_element)

            current_pos = url_match.end()

        # Add remaining text
        remaining_text = text[current_pos:]
        if remaining_text.strip():
            result.append({"text": remaining_text, "type": "text"})

        # If no URLs found, just return the text
        if not result and text.strip():
            result.append({"text": text, "type": "text"})

        return result

    def _parse_inline_tag(self, tag: Tag) -> list[dict[str, Any]]:
        """Parse inline HTML tags"""
        tag_name = tag.name.lower()

        # Handle different inline tags
        if tag_name == "a":
            # Handle links - check if they should have underline marks
            href = tag.get("href", "")
            text_content = tag.get_text()

            # Create basic link structure
            link_element = {
                "attrs": {"href": href},
                "content": [{"text": text_content, "type": "text"}],
                "type": "tiptap-link",
            }

            # Only add underline marks if the link has explicit underline styling or class
            if tag.get("style") and "text-decoration" in tag.get("style", ""):
                if "underline" in tag.get("style"):
                    link_element["marks"] = [{"type": "underline"}]
            elif "underline" in tag.get("class", []):
                link_element["marks"] = [{"type": "underline"}]

            return [link_element]

        # Get the text content for other tags
        text_content = tag.get_text()
        if not text_content.strip():
            return []

        # Handle other formatting tags
        marks = []
        if tag_name in ["strong", "b"]:
            marks.append({"type": "bold"})
        elif tag_name in ["em", "i"]:
            marks.append({"type": "italic"})
        elif tag_name in ["u"]:
            marks.append({"type": "underline"})

        # Handle nested formatting
        if tag.children and any(isinstance(child, Tag) for child in tag.children):
            content = []
            for child in tag.children:
                if isinstance(child, NavigableString):
                    text = str(child).strip()
                    if text:
                        text_element = {"text": text, "type": "text"}
                        if marks:
                            text_element["marks"] = marks.copy()
                        content.append(text_element)
                elif isinstance(child, Tag):
                    child_content = self._parse_inline_tag(child)
                    for item in child_content:
                        # Combine marks properly
                        if marks and item.get("marks"):
                            item["marks"] = marks + item["marks"]
                        elif marks and item.get("type") == "text":
                            item["marks"] = marks.copy()
                    content.extend(child_content)
            return content
        else:
            # Simple text with marks
            text_element = {"text": text_content, "type": "text"}
            if marks:
                text_element["marks"] = marks
            return [text_element]


def convert_html_to_rich_content(html_text: str) -> list[dict[str, Any]]:
    """
    Convert HTML text to rich content format.

    Args:
        html_text (str): The HTML text to convert

    Returns:
        List[Dict[str, Any]]: The rich content format
    """
    converter = HtmlToRichContentConverter()
    return converter.convert(html_text)


def add_license_key(rich_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add a license key to the rich content"""
    rich_content[0]["description"]["content"].append({"type": "licenseKey"})
    return rich_content


# Example usage
if __name__ == "__main__":
    sample_html = """
    <p><a href="https://dannymac.gumroad.com/l/hairwrangler?layout=discover&recommended_by=search">https://dannymac.gumroad.com/l/hairwrangler?layout=discover&recommended_by=search</a></p>
    
    <div>License Key</div>
    
    <h3><strong>Reimagine Hair Creation in Blender</strong></h3>
    
    <p>This is <strong>bold</strong> text and this is <em>italic</em> text with a standalone URL: https://example.com/another-link</p>
    
    <ul>
        <li><strong>Feature 1</strong> with bold text</li>
        <li><em>Feature 2</em> with italic text</li>
        <li>Feature 3 with <a href="https://example.com">a link</a></li>
    </ul>
    
    <blockquote>
        <p>This is a blockquote with <strong>bold</strong> text</p>
    </blockquote>
    
    <img src="https://example.com/image.jpg" alt="Sample Image">
    
    <hr>
    
    <p>That's all!</p>
    """

    result = convert_html_to_rich_content(sample_html)
    logger.info(json.dumps(result, indent=2))
