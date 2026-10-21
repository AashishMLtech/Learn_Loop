"""Tests for deterministic rubric validators."""
from evaluation.validators import (
    validate_beginner_readability,
    validate_citation_integrity,
    validate_code_integrity,
    validate_example_present,
    validate_jargon_control,
    validate_output_integrity,
    validate_teaching_flow_structure,
)
from generation.schema import (
    ComprehensionQuestion,
    GlossaryItem,
    Lesson,
    LessonStep,
    ReferenceItem,
    WorkedExample,
)
from shared.enums import CriterionStatus, LearnerLevel, LessonLength


def make_sample_lesson() -> Lesson:
    """Builds a standard valid lesson."""
    return Lesson(
        title="Binary Search Algorithm Essentials",
        introduction="Binary search is an efficient divide-and-conquer strategy for finding items in sorted collections. In this introductory lesson, we examine how the algorithm isolates elements in logarithmic time.",
        prerequisites=["Basic array indexing", "Concept of sorted sequences"],
        definition="Binary search is an algorithm that repeatedly divides a sorted search interval in half to locate a target value.",
        why_it_matters="It reduces search complexity from linear to logarithmic, allowing databases to query millions of records in milliseconds.",
        steps=[
            LessonStep(
                heading="Step 1: Setting Boundary Pointers",
                body="We assign low and high pointer markers to the beginning and end of the sorted array.",
            ),
            LessonStep(
                heading="Step 2: Checking the Middle Element",
                body="Calculate mid index and compare with the target. As observed in our worked example scenario, halving the range proceeds systematically until the match is confirmed.",
            ),
        ],
        worked_example=WorkedExample(
            scenario="Locating target value 7 in sorted array [1, 3, 5, 7, 9, 11].",
            walkthrough="1. Set low=0, high=5. Mid=2 with value 5. 2. Target 7 > 5, so low=3. 3. Mid=3 with value 7; match found at index 3.",
        ),
        key_distinctions=["Binary search requires sorted arrays, whereas linear search works on unsorted lists."],
        common_misunderstandings=["Binary search cannot be run on unsorted arrays."],
        glossary=[
            GlossaryItem(term="Logarithmic Time", definition="Efficiency where time scales with the logarithm of input size."),
            GlossaryItem(term="Midpoint", definition="The middle index computed between boundary pointers."),
        ],
        specialized_terms=["Logarithmic Time", "Midpoint"],
        summary="Binary search repeatedly halves the search space to find elements rapidly in O(log n) time. As shown in the worked example, comparing against the middle element rapidly eliminates half the dataset.",
        takeaways=[
            "Binary search requires sorted data.",
            "Each iteration discards half the remaining candidates.",
        ],
        comprehension_questions=[
            ComprehensionQuestion(question="What is the prerequisite for binary search?", answer="The array must be sorted."),
        ],
        references=[ReferenceItem(source_id="clrs-1", title="Introduction to Algorithms Chapter 2")],
    )


def test_output_integrity_valid():
    lesson = make_sample_lesson()
    res = validate_output_integrity(lesson, LessonLength.SHORT)
    assert res.status == CriterionStatus.PASS


def test_output_integrity_missing_fields():
    lesson = make_sample_lesson()
    lesson.title = ""
    res = validate_output_integrity(lesson, LessonLength.SHORT)
    assert res.status == CriterionStatus.FAIL
    assert "Missing title" in res.reason


def test_beginner_readability():
    lesson = make_sample_lesson()
    res = validate_beginner_readability(lesson, LearnerLevel.BEGINNER)
    assert res.status == CriterionStatus.PASS


def test_jargon_control_success():
    lesson = make_sample_lesson()
    res = validate_jargon_control(lesson)
    assert res.status == CriterionStatus.PASS


def test_jargon_control_missing_definition():
    lesson = make_sample_lesson()
    lesson.glossary[0].definition = ""
    res = validate_jargon_control(lesson)
    assert res.status == CriterionStatus.FAIL
    assert "without definition" in res.reason


def test_jargon_control_specialized_terms_undefined():
    lesson = make_sample_lesson()
    lesson.specialized_terms.append("UndefinedAlienConcept")
    res = validate_jargon_control(lesson)
    assert res.status == CriterionStatus.FAIL
    assert "UndefinedAlienConcept" in res.reason


def test_example_present_unreferenced():
    lesson = make_sample_lesson()
    lesson.steps = [LessonStep(heading="Step 1", body="Pointers are set.")]
    lesson.summary = "Binary search is finished."
    res = validate_example_present(lesson)
    assert res.status == CriterionStatus.FAIL
    assert "not referenced" in res.reason


def test_teaching_flow_empty_step_body():
    lesson = make_sample_lesson()
    lesson.steps[0].body = ""
    res = validate_teaching_flow_structure(lesson)
    assert res.status == CriterionStatus.FAIL


def test_code_integrity():
    lesson = make_sample_lesson()
    # Python code valid
    lesson.steps[0].body += "\n```python\ndef search():\n    return 42\n```"
    res = validate_code_integrity(lesson)
    assert res.status == CriterionStatus.PASS

    # Python code invalid
    lesson.steps[0].body += "\n```python\ndef broken(:\n```"
    res_err = validate_code_integrity(lesson)
    assert res_err.status == CriterionStatus.FAIL
    assert "Python code syntax error" in res_err.reason


def test_citation_integrity_matching_and_unmatched():
    lesson = make_sample_lesson()
    sources = [{"source_id": "clrs-1", "title": "Introduction to Algorithms Chapter 2"}]

    # Valid match
    res = validate_citation_integrity(lesson, supplied_sources=sources)
    assert res.status == CriterionStatus.PASS

    # Unmatched citation
    lesson.references.append(ReferenceItem(source_id="unauthorized-id", title="Fake Book"))
    res_unmatched = validate_citation_integrity(lesson, supplied_sources=sources)
    assert res_unmatched.status == CriterionStatus.FAIL
    assert "Fabricated citation" in res_unmatched.reason
