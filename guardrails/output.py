"""Output Guardrails and Markdown Sanitization Module.

Purpose:
    Sanitizes markdown content prior to rendering or API return, neutralizing
    raw HTML tags, scripts, iframes, and javascript: URL schemes to prevent XSS.

Inputs/Outputs:
    Inputs: Raw generated markdown strings or Lesson text.
    Outputs: Safe, sanitized markdown string.

What it must NOT do:
    - Must NOT allow executable JavaScript, iframes, or unsafe HTML.
    - Must NOT corrupt legitimate markdown syntax (headers, bullet points, code blocks).
"""
import re

DANGEROUS_TAGS_PATTERN = re.compile(
    r"<\s*(script|iframe|embed|object|style|form|input|button|meta|link)[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

SELF_CLOSING_DANGEROUS_TAGS = re.compile(
    r"<\s*(script|iframe|embed|object|style|form|input|button|meta|link)[^>]*\/?>",
    re.IGNORECASE,
)

EVENT_HANDLER_PATTERN = re.compile(r"on\w+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE)

JAVASCRIPT_URL_PATTERN = re.compile(r"\[([^\]]+)\]\(\s*javascript:[^\)]*\)", re.IGNORECASE)


def sanitize_markdown(markdown_text: str) -> str:
    """Sanitizes Markdown by removing dangerous HTML tags and javascript: links.

    Args:
        markdown_text: Raw markdown content.

    Returns:
        Sanitized markdown string safe for rendering.
    """
    if not markdown_text:
        return ""

    sanitized = markdown_text

    # 1. Remove paired dangerous tags with contents
    sanitized = DANGEROUS_TAGS_PATTERN.sub("", sanitized)

    # 2. Remove self-closing dangerous tags
    sanitized = SELF_CLOSING_DANGEROUS_TAGS.sub("", sanitized)

    # 3. Strip inline event handlers (e.g. onload, onerror)
    sanitized = EVENT_HANDLER_PATTERN.sub("", sanitized)

    # 4. Neutralize javascript: URL schemes in markdown links [click](javascript:alert(1))
    sanitized = JAVASCRIPT_URL_PATTERN.sub(r"[\1](#blocked-unsafe-javascript-url)", sanitized)

    return sanitized
