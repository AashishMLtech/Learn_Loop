"""Scan Source Code For Forbidden Hardcoded Demo-Topic Strings.

Purpose:
    Enforces that 'Introduction to RAG' is treated strictly as an external demo input
    and no topic-specific strings or prompts are hardcoded in the codebase.
"""
import re
from pathlib import Path

FORBIDDEN_TOPIC_PATTERNS = [
    r"\bRAG\b",
    r"retrieval[-\s]augmented\s+generation",
]

EXCLUDED_PARTS = {
    "docs",
    "fixtures",
    "demo_rejection.py",
    "test_no_hardcoded_topic.py",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}


def test_no_hardcoded_demo_topic():
    """Scans source tree (excluding docs, fixtures, demo_rejection.py) for demo-topic strings."""
    root_dir = Path(__file__).resolve().parent.parent
    violations = []
    regexes = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_TOPIC_PATTERNS]

    for ext in ("*.py", "*.yaml", "*.md"):
        for path in root_dir.rglob(ext):
            parts = set(path.parts)
            if parts.intersection(EXCLUDED_PARTS) or path.name in EXCLUDED_PARTS:
                continue

            content = path.read_text(encoding="utf-8", errors="ignore")
            for idx, line in enumerate(content.splitlines(), 1):
                for reg in regexes:
                    if reg.search(line):
                        violations.append(f"{path.relative_to(root_dir)}:{idx} -> {line.strip()}")

    assert not violations, "Forbidden demo-topic strings found in source code:\n" + "\n".join(violations)
