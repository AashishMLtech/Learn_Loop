Status: implemented

# Data Model Documentation

## Overview
Persistence is managed via SQLAlchemy 2.x ORM models mapped to SQLite (or PostgreSQL via `DATABASE_URL`).

## Database Tables and Entities

### 1. `runs` (`RunModel`)
Represents an individual lesson generation job.
- `id`: String(36) UUID primary key.
- `topic`: String(300), educational topic.
- `learner_level`: String(50), e.g. beginner, intermediate.
- `objectives`: JSON list of string objectives.
- `target_length`: String(50), e.g. short, medium, long.
- `max_retries`: Integer, clamped to [0, 2].
- `status`: String(50), e.g. RUNNING, PASS, REJECTED, ERROR, CANCELLED.
- `self_judged`: Boolean, always True.
- `not_externally_verified`: Boolean, always True.
- `hint_version`: Optional String(50), tracking Level A pitfall hints.
- `cancel_requested`: Boolean, flag checked before LLM calls.
- `error_message`: Optional Text.
- `final_lesson_id`: Optional String(36), foreign key to passing `lesson_versions.id`.
- `created_at`, `updated_at`: UTC timestamps.

### 2. `lesson_versions` (`LessonVersionModel`)
Snapshots each generation/revision iteration.
- `id`: String(36) UUID primary key.
- `run_id`: Foreign key to `runs.id`.
- `version_number`: Integer iteration index (1, 2, ...).
- `content`: JSON representation of Pydantic `Lesson`.
- `changes_made`: JSON list of revision changes made.
- `created_at`: UTC timestamp.

### 3. `evaluations` (`EvaluationModel`)
Stores evaluation audit records per version.
- `id`: String(36) UUID primary key.
- `run_id`: Foreign key to `runs.id`.
- `lesson_version_id`: Foreign key to `lesson_versions.id`.
- `rubric_version`: String(20).
- `judge_model`: String(100).
- `criterion_results`: JSON list of 13 criterion results.
- `claims`: JSON list of extracted claims.
- `passed`: Boolean release gate verdict.
- `created_at`: UTC timestamp.

### 4. `rejection_log` (`RejectionLogModel`)
Audit log recording every rejection event.
- `id`: String(36) UUID primary key.
- `run_id`: Foreign key to `runs.id`.
- `attempt`: Integer attempt number.
- `failed_criteria`: JSON list of failed criterion IDs.
- `reasons`: JSON list of explanatory reasons.
- `changes_made`: JSON list of requested or applied fixes.
- `result`: String(50), e.g. REJECTED, RETRYING, PASS.

### 5. `token_usage` (`TokenUsageModel`)
Fine-grained token accounting per LLM invocation.
- `id`: String(36) UUID primary key.
- `run_id`: Foreign key to `runs.id`.
- `attempt`: Integer attempt index.
- `call_type`: String(50), e.g. generate, revise, judge.
- `model`: String(100).
- `prompt_tokens`, `completion_tokens`, `total_tokens`: Integer counts.

### 6. `feedback` (`FeedbackModel`)
User ratings and evaluations.
- `id`: String(36) UUID primary key.
- `run_id`: Foreign key to `runs.id`.
- `rating`: Integer (1-5 stars).
- `issue_tags`: JSON list of tags.
- `comment`: Optional Text comment.

### 7. `proposals` (`ProposalModel`) & `prompt_versions` (`PromptVersionModel`)
Level B self-evolving governance tables storing proposed amendments and approval states.

## How to modify this
To modify database models, edit `memory/store.py` and run schema migrations or recreate tables using `init_db()`.
