You are an expert instructional designer and technical educator.
Generate a comprehensive, standalone beginner lesson for the topic specified below.

## Topic
{topic}

## Learner Target Level
{learner_level}

## Learning Objectives
{learning_objectives}

## Target Length
{target_length}

## Common Pitfalls To Avoid (from historical evaluation patterns)
{pitfall_hints}

## Authorized Supplied Sources
{supplied_sources}

## Reference Material (Context)
{reference_context}

## Instructions
1. Ensure the lesson is clear, self-contained, and suitable for a beginner.
2. Every specialized term introduced in `specialized_terms` MUST appear in the glossary or be defined inline at first use.
3. The `worked_example` MUST be populated and explicitly referenced in the steps or summary.
4. If Python code snippets are used, ensure they are syntactically valid.
5. In `references`, include ONLY citations matching the supplied sources. If no sources are supplied, leave references empty.
6. Return raw JSON matching the required schema.

## Output Schema
{{
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
}}
Return raw JSON only.
