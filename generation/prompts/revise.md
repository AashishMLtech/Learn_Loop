You are an expert educational editor improving a lesson draft that failed quality criteria.

## Topic
{topic}

## Learner Target Level
{learner_level}

## Learning Objectives
{learning_objectives}

## Previous Lesson Draft
{previous_lesson_json}

## Evaluation Failures To Fix
{failure_feedback}

## Instructions
1. Review the failure feedback and resolve all reported issues.
2. If jargon was flagged, define it inline or add it to the glossary.
3. If the worked example was not referenced, ensure it is clearly connected in the steps or summary.
4. If citation integrity failed, remove any unauthorized citations or URLs.
5. In the same response, return BOTH the complete revised lesson and a list of specific changes made.

## Output Schema
{{
  "lesson": {{
    "title": "string",
    "introduction": "string",
    "prerequisites": ["string"],
    "definition": "string",
    "why_it_matters": "string",
    "steps": [{{"heading": "string", "body": "string"}}],
    "worked_example": {{"scenario": "string", "walkthrough": "string"}},
    "key_distinctions": ["string"],
    "common_misunderstandings": ["string"],
    "glossary": [{{"term": "string", "definition": "string"}}],
    "specialized_terms": ["string"],
    "summary": "string",
    "takeaways": ["string"],
    "comprehension_questions": [{{"question": "string", "answer": "string"}}],
    "references": [{{"source_id": "string", "title": "string"}}]
  }},
  "changes_made": [
    "string describing edit 1",
    "string describing edit 2"
  ]
}}
Return raw JSON only.
