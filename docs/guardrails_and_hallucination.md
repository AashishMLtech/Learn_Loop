Status: implemented

# Guardrails and Hallucination Control Documentation

## Input Guardrails (`guardrails/input.py`)
1. **Request Validation**:
   - Topic strings constrained to [1, 300] characters.
   - Objectives list constrained to [1, 10] non-empty goals.
   - Retries clamped strictly between 0 and 2.
2. **File Upload Boundaries**:
   - File extensions limited to `.txt` and `.md`.
   - File size capped at 200 KB per upload.
   - UTF-8 decoding strictly enforced.
3. **Prompt Injection Screening**:
   - Regex-based adversarial pattern scanning detects system prompt overrides, jailbreaks, and instructions attempting to bypass evaluation.
   - Flagged phrases are neutralized with `[REDACTED_ADVERSARIAL_INJECTION_PATTERN]`.

## Output Guardrails (`guardrails/output.py`)
- HTML/Markdown sanitization strips `<script>`, `<iframe>`, `<object>`, `<embed>`, `<applet>`, and `<form>` tags.
- Disallowed URI protocols (`javascript:`, `vbscript:`, `data:`) are sanitized to prevent cross-site scripting in the UI renderer.

## Hallucination Mitigation & Claim Grounding (`hallucination/claims.py`)
1. **Untrusted Block Delimiters**:
   - Reference document excerpts retrieved via keyword overlap are framed with explicit untrusted delimiter blocks:
     `=== BEGIN UNTRUSTED REFERENCE DATA (SOURCE ID: ...) ===`
     instructing models to treat text strictly as factual reference data, not executable directives.
2. **Deterministic Citation Verification**:
   - All citations extracted by the judge are verified against supplied documents.
   - Evidence quotes are verified as literal normalized substrings of the source text.
   - Unsupplied source IDs or fabricated quotes cause the claim to be marked `UNSUPPORTED` with a fabrication error.
3. **Elementary Math Claims Verification**:
   - Mathematical claims containing parseable equations (e.g., `12 * 12 = 144`) are extracted and evaluated with SymPy.
   - Discrepancies (e.g., `50 / 2 = 35`) are flagged as contradicted statements.

## How to modify this
To update guardrail rules or add screening patterns, modify `guardrails/input.py`, `guardrails/output.py`, and `hallucination/claims.py`.
