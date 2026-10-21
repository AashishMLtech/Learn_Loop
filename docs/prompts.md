Status: implemented

# Prompts Engineering Documentation

## Overview
All prompt templates are stored in versioned markdown files and adhere to topic-agnostic structures. No educational topic is hardcoded in any prompt file.

## Prompt Files

### 1. `generation/prompts/generate.md`
- **Purpose**: Generates the initial lesson draft conforming to the Pydantic `Lesson` schema.
- **Parameters**: `topic`, `learner_level`, `objectives_block`, `target_length`, `length_bounds_hint`, `pitfall_hints_block`, `reference_context_block`.
- **Key Directives**:
  - Requires worked example with scenario and walkthrough.
  - Requires all specialized terms to be defined in the glossary or inline.
  - Directs model to respect target word count bounds.
  - Formats output strictly within a ````json ``` code fence.

### 2. `generation/prompts/revise.md`
- **Purpose**: Revises a failed lesson draft using specific rejection feedback and failed criteria.
- **Parameters**: `topic`, `learner_level`, `target_length`, `previous_lesson_json`, `rejection_feedback_block`, `pitfall_hints_block`, `reference_context_block`.
- **Key Directives**:
  - Instructs model to address every failed criterion explicitly.
  - Requires summarizing changes made in the `changes_made` field.
  - Forbids regressing on previously passing sections.

### 3. `evaluation/prompts/judge.md`
- **Purpose**: Executes the combined structured evaluation call.
- **Parameters**: `topic`, `learner_level`, `target_length`, `objectives_block`, `lesson_json`, `evidence_mode`, `reference_context_block`.
- **Key Directives**:
  - Evaluates the 6 LLM-judged criteria: `factual_accuracy`, `internal_consistency`, `example_correctness`, `topic_coverage`, `coherence_of_flow`, `standalone_completeness`.
  - Extracts atomic material claims with claim taxonomy type (`factual`, `definitional`, `procedural`, `mathematical`).
  - Strict binary PASS/FAIL verdicts per criterion with evidence and suggested fixes.

## How to modify this
To modify prompt templates, edit `generation/prompts/generate.md`, `generation/prompts/revise.md`, or `evaluation/prompts/judge.md` while preserving required JSON schema keys.
