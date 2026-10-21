"""Lesson Pydantic Schema Specification.

Purpose:
    Defines the canonical Pydantic v2 data model for instructional lessons,
    sub-components (steps, worked example, glossary, questions, references),
    and composite revision outputs.

Inputs/Outputs:
    Inputs: Raw validated dictionary data from LLM responses or storage.
    Outputs: Strongly-typed Pydantic Lesson and LessonRevisionOutput objects.

What it must NOT do:
    - Must NOT perform LLM generation or evaluation.
    - Must NOT hardcode topic-specific fields.
"""
from typing import List

from pydantic import BaseModel, Field


class LessonStep(BaseModel):
    """An ordered step in the instructional body of the lesson."""
    heading: str = Field(..., description="Descriptive title of the step")
    body: str = Field(..., description="Detailed instructional explanation")


class WorkedExample(BaseModel):
    """A concrete worked example illustrating the concept (always required)."""
    scenario: str = Field(..., description="Contextual problem or scenario")
    walkthrough: str = Field(..., description="Step-by-step resolution or demonstration")


class GlossaryItem(BaseModel):
    """A glossary term and its definition."""
    term: str = Field(..., description="Specialized or technical term")
    definition: str = Field(..., description="Clear plain-language definition")


class ComprehensionQuestion(BaseModel):
    """A self-check question with its corresponding answer."""
    question: str = Field(..., description="Conceptual question")
    answer: str = Field(..., description="Accurate model answer")


class ReferenceItem(BaseModel):
    """A citation referencing an authorized supplied source."""
    source_id: str = Field(..., description="Identifier matching supplied source ID")
    title: str = Field(..., description="Title of the source")


class Lesson(BaseModel):
    """Canonical lesson schema adhering strictly to Section 4 design specifications."""
    title: str = Field(..., description="Lesson title")
    introduction: str = Field(..., description="Context setting and motivation")
    prerequisites: List[str] = Field(default_factory=list, description="Recommended prior knowledge")
    definition: str = Field(..., description="Core formal definition of the topic")
    why_it_matters: str = Field(..., description="Practical real-world significance")
    steps: List[LessonStep] = Field(..., min_length=1, description="Ordered instructional steps")
    worked_example: WorkedExample = Field(..., description="Mandatory worked example")
    key_distinctions: List[str] = Field(default_factory=list, description="Distinctions from related concepts")
    common_misunderstandings: List[str] = Field(default_factory=list, description="Common misconceptions")
    glossary: List[GlossaryItem] = Field(default_factory=list, description="Glossary of terms")
    specialized_terms: List[str] = Field(
        default_factory=list, description="Terms the generator flags as jargon or specialized vocabulary"
    )
    summary: str = Field(..., description="Synthesis of core concepts")
    takeaways: List[str] = Field(default_factory=list, min_length=1, description="Key bulleted takeaways")
    comprehension_questions: List[ComprehensionQuestion] = Field(
        default_factory=list, description="Self-check comprehension questions"
    )
    references: List[ReferenceItem] = Field(
        default_factory=list, description="Citations only from supplied sources; may be empty"
    )

    def full_text(self) -> str:
        """Concatenates all prose sections for word count and readability grading.

        Returns:
            Complete text string of all lesson components.
        """
        parts: List[str] = [
            self.title,
            self.introduction,
            " ".join(self.prerequisites),
            self.definition,
            self.why_it_matters,
        ]
        for step in self.steps:
            parts.append(step.heading)
            parts.append(step.body)
        parts.append(self.worked_example.scenario)
        parts.append(self.worked_example.walkthrough)
        parts.extend(self.key_distinctions)
        parts.extend(self.common_misunderstandings)
        for g in self.glossary:
            parts.append(f"{g.term}: {g.definition}")
        parts.append(self.summary)
        parts.extend(self.takeaways)
        for q in self.comprehension_questions:
            parts.append(f"{q.question} {q.answer}")
        for r in self.references:
            parts.append(f"{r.source_id}: {r.title}")
        return "\n\n".join(parts)

    def word_count(self) -> int:
        """Calculates total word count across all textual fields.

        Returns:
            Integer word count.
        """
        return len(self.full_text().split())


class LessonRevisionOutput(BaseModel):
    """Combined schema returned by revision calls containing the revised lesson and changes made."""
    lesson: Lesson = Field(..., description="The revised lesson")
    changes_made: List[str] = Field(
        ..., min_length=1, description="Specific edits made in response to failure feedback"
    )
