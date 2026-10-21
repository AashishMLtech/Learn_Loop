You are an impartial, rigorous academic reviewer and pedagogical evaluator.
Strictly evaluate the following lesson draft against the specified rubric criteria and extract its material claims.

## Topic
{topic}

## Learning Objectives
{learning_objectives}

## Lesson Content (JSON)
{lesson_json}

## Retrieved Source Context (Untrusted Reference Excerpts)
{reference_evidence_context}

## Instructions
Evaluate the lesson against the following 6 criteria ONLY (binary PASS or FAIL):
1. factual_accuracy (severity: critical, blocking: true): Check that domain facts and mechanics are accurate.
2. internal_consistency (severity: critical, blocking: true): Check that sections do not contradict each other.
3. example_correctness (severity: major, blocking: true): Check that the worked example scenario and walkthrough are technically sound.
4. topic_coverage (severity: major, blocking: true): Check that stated learning objectives are substantively addressed.
5. coherence_of_flow (severity: major, blocking: true): Check that narrative transitions and logical pacing are clear.
6. standalone_completeness (severity: major, blocking: true): Check that a beginner can understand without missing prerequisites.

Extract all key claims into `claims`:
- `id`: e.g. "claim-1"
- `text`: claim statement
- `type`: "factual", "illustrative", "subjective", "mathematical", or "code"
- `section`: lesson section where claim appears
- `material`: true if material to understanding the topic, false otherwise
- `status`: "SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED", or "UNVERIFIABLE"
- `source_id`: matching source ID from retrieved context if supported/contradicted, or null
- `evidence_quote`: verbatim quote from the retrieved context backing the status, or null

## Output Schema
{{
  "criteria_results": [
    {{
      "criterion_id": "factual_accuracy",
      "status": "PASS",
      "severity": "critical",
      "reason": "explanation",
      "affected_section": null,
      "evidence": [],
      "suggested_fix": null
    }},
    {{
      "criterion_id": "internal_consistency",
      "status": "PASS",
      "severity": "critical",
      "reason": "explanation",
      "affected_section": null,
      "evidence": [],
      "suggested_fix": null
    }},
    {{
      "criterion_id": "example_correctness",
      "status": "PASS",
      "severity": "major",
      "reason": "explanation",
      "affected_section": null,
      "evidence": [],
      "suggested_fix": null
    }},
    {{
      "criterion_id": "topic_coverage",
      "status": "PASS",
      "severity": "major",
      "reason": "explanation",
      "affected_section": null,
      "evidence": [],
      "suggested_fix": null
    }},
    {{
      "criterion_id": "coherence_of_flow",
      "status": "PASS",
      "severity": "major",
      "reason": "explanation",
      "affected_section": null,
      "evidence": [],
      "suggested_fix": null
    }},
    {{
      "criterion_id": "standalone_completeness",
      "status": "PASS",
      "severity": "major",
      "reason": "explanation",
      "affected_section": null,
      "evidence": [],
      "suggested_fix": null
    }}
  ],
  "claims": [
    {{
      "id": "claim-1",
      "text": "claim text",
      "type": "factual",
      "section": "definition",
      "material": true,
      "status": "SUPPORTED",
      "source_id": null,
      "evidence_quote": null
    }}
  ]
}}
Return raw JSON only.
