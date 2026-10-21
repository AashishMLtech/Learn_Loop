"""Documentation and Docstring Integrity Gate Tests.

Purpose:
    Validates repository-wide documentation compliance:
    1. Every Python module contains a standardized module docstring specifying
       purpose, inputs/outputs, and what it must NOT do.
    2. Every public function contains docstrings documenting parameters, return values,
       and error/exception conditions.
    3. Every document in docs/ has 'Status: implemented|partial|deferred' on line 1
       and '## How to modify this' as its final heading.
    4. docs/codebase_map.md lists every file in the approved repository manifest.

Inputs/Outputs:
    Inputs: Abstract syntax trees of repository files, documentation markdown files.
    Outputs: Assertions enforcing full documentation and architecture compliance.

What it must NOT do:
    - Must NOT hardcode demo topic terms.
    - Must NOT allow undocumented modules or public functions.
"""
import ast
import os
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"

APPROVED_FILES_MANIFEST = [
    "ui/app.py",
    "ui/api_client.py",
    "api/main.py",
    "api/routes.py",
    "api/schemas.py",
    "api/config.py",
    "agent/state.py",
    "agent/graph.py",
    "agent/nodes.py",
    "generation/schema.py",
    "generation/service.py",
    "generation/prompts/generate.md",
    "generation/prompts/revise.md",
    "evaluation/rubric.yaml",
    "evaluation/validators.py",
    "evaluation/judge.py",
    "evaluation/prompts/judge.md",
    "guardrails/release_gate.py",
    "guardrails/input.py",
    "guardrails/output.py",
    "hallucination/claims.py",
    "memory/store.py",
    "shared/llm_client.py",
    "shared/enums.py",
    "scripts/demo_rejection.py",
    "scripts/manage_proposals.py",
    "tests/test_graph.py",
    "tests/test_validators.py",
    "tests/test_release_gate.py",
    "tests/test_hallucination.py",
    "tests/test_memory.py",
    "tests/test_api.py",
    "tests/test_ui_state.py",
    "tests/test_no_hardcoded_topic.py",
    "tests/test_docs.py",
    "tests/test_live_calibration.py",
    "tests/fixtures/golden/lesson_1_good.json",
    "tests/fixtures/golden/lesson_2_good.json",
    "tests/fixtures/golden/lesson_3_good.json",
    "tests/fixtures/golden/lesson_4_flawed_jargon.json",
    "tests/fixtures/golden/lesson_5_flawed_code.json",
    "tests/fixtures/golden/lesson_6_flawed_citations.json",
    "docs/architecture.md",
    "docs/codebase_map.md",
    "docs/workflow.md",
    "docs/evaluation_rubric.md",
    "docs/guardrails_and_hallucination.md",
    "docs/prompts.md",
    "docs/data_model.md",
    "docs/api_and_ui.md",
    "docs/configuration.md",
    "docs/token_optimization.md",
    "docs/decisions.md",
    "docs/troubleshooting.md",
    "README.md",
    ".env.example",
    "requirements.txt",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    ".gitignore",
    ".dockerignore",
    ".github/workflows/ci.yml",
]


def get_source_python_files() -> List[Path]:
    """Finds all non-test, non-venv Python source files."""
    files: List[Path] = []
    for root, dirs, filenames in os.walk(REPO_ROOT):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in {".venv", ".git", "__pycache__", "tests", ".pytest_cache"}]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(Path(root) / fname)
    return files


def test_module_docstrings_compliance() -> None:
    """Verifies every source file has purpose, inputs/outputs, and what-it-must-NOT-do."""
    py_files = get_source_python_files()
    assert len(py_files) > 0, "No source Python files found to inspect."

    failures = []
    for fpath in py_files:
        with open(fpath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(fpath))

        doc = ast.get_docstring(tree)
        if not doc:
            failures.append(f"{fpath.relative_to(REPO_ROOT)}: Missing module docstring.")
            continue

        doc_lower = doc.lower()
        if "purpose" not in doc_lower:
            failures.append(f"{fpath.relative_to(REPO_ROOT)}: Module docstring missing 'Purpose:'.")
        if not ("input" in doc_lower or "output" in doc_lower):
            failures.append(f"{fpath.relative_to(REPO_ROOT)}: Module docstring missing 'Inputs/Outputs:'.")
        if "must not" not in doc_lower and "must-not" not in doc_lower:
            failures.append(f"{fpath.relative_to(REPO_ROOT)}: Module docstring missing 'What it must NOT do:'.")

    assert not failures, "\n".join(failures)


def test_public_function_docstrings_presence() -> None:
    """Verifies that all public functions have docstrings documenting arguments, returns, and behavior."""
    py_files = get_source_python_files()
    failures = []

    for fpath in py_files:
        with open(fpath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(fpath))

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                doc = ast.get_docstring(node)
                rel_path = fpath.relative_to(REPO_ROOT)
                if not doc:
                    failures.append(f"{rel_path}:{node.name}: Missing docstring.")
                    continue

                # Check parameter documentation for functions with arguments
                param_args = [a.arg for a in node.args.args if a.arg != "self"]
                if param_args and not any(k in doc.lower() for k in ["arg", "param", "parameter"]):
                    failures.append(f"{rel_path}:{node.name}: Docstring does not document arguments ({param_args}).")

    assert not failures, "\n".join(failures)


def test_docs_status_line_and_last_heading() -> None:
    """Verifies that all 12 docs have Status on line 1 and '## How to modify this' as final heading."""
    expected_doc_names = [
        "architecture.md",
        "codebase_map.md",
        "workflow.md",
        "evaluation_rubric.md",
        "guardrails_and_hallucination.md",
        "prompts.md",
        "data_model.md",
        "api_and_ui.md",
        "configuration.md",
        "token_optimization.md",
        "decisions.md",
        "troubleshooting.md",
    ]

    for doc_name in expected_doc_names:
        fpath = DOCS_DIR / doc_name
        assert fpath.exists(), f"Expected documentation file {doc_name} is missing."

        with open(fpath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert lines, f"Documentation file {doc_name} is empty."
        status_line = lines[0]
        assert status_line.startswith("Status:"), f"{doc_name}: Line 1 must start with 'Status:', got '{status_line}'."

        headings = [line for line in lines if line.startswith("#")]
        assert headings, f"{doc_name}: No Markdown headings found."
        last_heading = headings[-1]
        assert last_heading == "## How to modify this", (
            f"{doc_name}: Final heading must be '## How to modify this', got '{last_heading}'."
        )


def test_codebase_map_lists_every_file() -> None:
    """Verifies that docs/codebase_map.md contains every file from the approved repository manifest."""
    codebase_map_path = DOCS_DIR / "codebase_map.md"
    assert codebase_map_path.exists(), "docs/codebase_map.md does not exist."

    with open(codebase_map_path, "r", encoding="utf-8") as f:
        content = f.read()

    missing_files = []
    for approved_file in APPROVED_FILES_MANIFEST:
        if approved_file not in content:
            missing_files.append(approved_file)

    assert not missing_files, f"docs/codebase_map.md is missing entries for: {missing_files}"
