"""NiceGUI Frontend Application Module.

Purpose:
    Renders the responsive web interface for Learn Loop, an autonomous closed-loop
    educational lesson generator styled in a luxury Deep Navy, Warm Beige, and Soft Gold
    design system with an expansive, screen-optimized desktop layout.
    Provides Create, Run Status, Iteration History, and Global Metrics dashboards.
    Communicates exclusively with the FastAPI backend over HTTP via ApiClient.

Inputs/Outputs:
    Inputs: User interaction events (form inputs, file uploads, navigation clicks).
    Outputs: Visual UI elements, polled state updates, and formatted lesson previews.

What it must NOT do:
    - Must NOT execute generation or evaluation logic directly.
    - Must NOT connect directly to the database or LLM providers.
    - Must NOT hardcode demo topic terms.
"""
import json
import logging
import os
import sys
from typing import Any, Dict

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nicegui import ui

from ui.api_client import ApiClient, ApiClientError

logger = logging.getLogger("lesson_generator.ui")
client = ApiClient()

# ==========================================
# Design System Styles (Navy, Beige, Soft Gold)
# ==========================================

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,400&display=swap');

:root {
    --navy-dark: #0B132B;
    --navy-surface: #1C2541;
    --navy-light: #2A3656;
    --beige-bg: #FAF7F2;
    --beige-surface: #FFFFFF;
    --beige-muted: #F4EFEA;
    --beige-border: #E8DFD1;
    --gold-primary: #C5A059;
    --gold-light: #DFB15B;
    --gold-subtle: #F3E5AB;
    --gold-dark: #9A7B38;
}

body {
    background-color: var(--beige-bg) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #1E293B;
    margin: 0;
    padding: 0;
}

.font-editorial {
    font-family: 'Playfair Display', Georgia, serif;
}

/* Custom Cards */
.editorial-card {
    background-color: var(--beige-surface);
    border: 1px solid var(--beige-border);
    border-radius: 16px;
    box-shadow: 0 4px 20px -2px rgba(11, 19, 43, 0.05);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.editorial-card:hover {
    box-shadow: 0 8px 30px -4px rgba(11, 19, 43, 0.08);
}

.navy-hero-card {
    background: linear-gradient(135deg, #0B132B 0%, #1C2541 100%);
    border: 1px solid rgba(197, 160, 89, 0.3);
    border-radius: 20px;
    color: #FFFFFF;
    box-shadow: 0 10px 30px -5px rgba(11, 19, 43, 0.2);
}

/* Gold Accents & Buttons */
.gold-btn {
    background: linear-gradient(135deg, #C5A059 0%, #DFB15B 100%) !important;
    color: #0B132B !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    letter-spacing: 0.025em;
    transition: all 0.2s ease !important;
}

.gold-btn:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(197, 160, 89, 0.4) !important;
}

.navy-btn {
    background: #0B132B !important;
    color: #F3E5AB !important;
    border: 1px solid #C5A059 !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    transition: all 0.2s ease !important;
}

.navy-btn:hover {
    background: #1C2541 !important;
    box-shadow: 0 4px 15px rgba(11, 19, 43, 0.3) !important;
}

/* Worked Example Callout */
.worked-example-box {
    background-color: #F8F5EE;
    border-left: 4px solid var(--gold-primary);
    border-radius: 0 12px 12px 0;
    padding: 16px 20px;
}

/* Pulsing Badge for Active Runs */
@keyframes pulseGlow {
    0% { box-shadow: 0 0 0 0 rgba(197, 160, 89, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(197, 160, 89, 0); }
    100% { box-shadow: 0 0 0 0 rgba(197, 160, 89, 0); }
}

.pulse-badge {
    animation: pulseGlow 2s infinite;
}
</style>
"""


def render_header() -> None:
    """Renders the common luxury navigation header bar.

    Returns:
        None
    """
    ui.add_head_html(THEME_CSS)
    with ui.header().classes("w-full items-center justify-between px-8 lg:px-16 py-4 shadow-md").style(
        "background: linear-gradient(90deg, #0B132B 0%, #152238 100%); border-bottom: 2px solid #C5A059;"
    ):
        with ui.row().classes("items-center gap-4"):
            ui.icon("auto_stories", size="md").classes("text-[#DFB15B]")
            with ui.column().classes("gap-0"):
                ui.label("LEARN LOOP").classes("font-editorial text-2xl font-bold tracking-wider text-white")
                ui.label("Autonomous Closed-Loop Pedagogical Engine").classes("text-xs tracking-widest text-[#F3E5AB] uppercase")

        with ui.row().classes("gap-8 items-center text-sm font-semibold"):
            ui.link("CREATE LESSON", "/").classes("text-[#F4EFEA] hover:text-[#DFB15B] transition-colors")
            ui.link("RUN ARCHIVE", "/history").classes("text-[#F4EFEA] hover:text-[#DFB15B] transition-colors")
            ui.link("QUALITY METRICS", "/metrics").classes("text-[#F4EFEA] hover:text-[#DFB15B] transition-colors")


def render_disclaimers() -> None:
    """Renders mandatory system disclaimers in a refined warm card.

    Returns:
        None
    """
    with ui.card().classes("w-full p-4 mb-2 rounded-xl").style(
        "background-color: #FBF8F2; border: 1px solid #E8DFD1; border-left: 4px solid #C5A059;"
    ):
        with ui.row().classes("items-center gap-2 text-[#0B132B] font-bold text-xs uppercase tracking-wider"):
            ui.icon("verified_user", size="xs").classes("text-[#C5A059]")
            ui.label("Evaluation & Grounding Disclaimers")
        ui.label("• Self-judged by model; not externally verified.").classes("text-[#475569] text-xs mt-1")
        ui.label("• Never claim zero hallucinations.").classes("text-[#475569] text-xs")


# ==========================================
# Page: Create Lesson (/)
# ==========================================

@ui.page("/")
def create_page() -> None:
    """Renders the lesson generation request creation page with expansive two-column layout.

    Returns:
        None
    """
    render_header()

    uploaded_reference: Dict[str, str] = {}

    with ui.column().classes("w-full max-w-[1500px] mx-auto px-6 lg:px-12 py-8 gap-8"):
        # Hero Introduction Banner
        with ui.card().classes("w-full p-8 navy-hero-card"):
            with ui.row().classes("items-center justify-between w-full"):
                with ui.column().classes("max-w-3xl gap-2"):
                    ui.label("Architect Precision Educational Lessons").classes("font-editorial text-3xl lg:text-4xl font-bold text-white")
                    ui.label(
                        "Autonomous curriculum synthesis powered by closed-loop verification. "
                        "Generates educational modules, evaluates them across 13 rigorous criteria, and self-corrects on failure."
                    ).classes("text-sm text-[#F4EFEA] leading-relaxed")
                ui.icon("psychology", size="4.5rem").classes("text-[#C5A059] opacity-80 hidden md:block")

            # Quick Suggestion Chips
            ui.label("Quick Presets (Click to Load):").classes("text-xs font-semibold text-[#F3E5AB] uppercase tracking-wider mt-4")
            with ui.row().classes("gap-3 mt-1 flex-wrap"):
                def set_preset(t: str, objs: str) -> None:
                    topic_input.set_value(t)
                    objectives_input.set_value(objs)
                    ui.notify(f"Loaded preset: {t}", type="info")

                ui.button(
                    "Machine Learning",
                    on_click=lambda: set_preset(
                        "Foundations of Machine Learning",
                        "1. Understand supervised vs unsupervised learning\n2. Learn model training and loss minimization\n3. Distinguish overfitting from generalization",
                    ),
                ).props("flat dense").classes("text-xs text-[#F3E5AB] bg-white/10 hover:bg-white/20 rounded-full px-4 py-1.5")

                ui.button(
                    "Vector Embeddings",
                    on_click=lambda: set_preset(
                        "Vector Embeddings and Semantic Representation",
                        "1. Understand high-dimensional numerical vectors\n2. Learn semantic distance and cosine similarity\n3. Examine real-world text encoding workflows",
                    ),
                ).props("flat dense").classes("text-xs text-[#F3E5AB] bg-white/10 hover:bg-white/20 rounded-full px-4 py-1.5")

                ui.button(
                    "Vector Databases",
                    on_click=lambda: set_preset(
                        "Vector Databases and Similarity Search",
                        "1. Understand approximate nearest neighbor (ANN) search\n2. Learn HNSW graph indexing concepts\n3. Differentiate scalar filtering from vector search",
                    ),
                ).props("flat dense").classes("text-xs text-[#F3E5AB] bg-white/10 hover:bg-white/20 rounded-full px-4 py-1.5")

                ui.button(
                    "Large Language Models",
                    on_click=lambda: set_preset(
                        "Architecture of Large Language Models",
                        "1. Understand transformer self-attention mechanisms\n2. Learn tokenization and probabilistic next-token generation\n3. Examine pre-training versus fine-tuning",
                    ),
                ).props("flat dense").classes("text-xs text-[#F3E5AB] bg-white/10 hover:bg-white/20 rounded-full px-4 py-1.5")

        # Two-Column Desktop Layout
        with ui.row().classes("w-full gap-8 items-start"):
            # Left Column (7/12 width on desktop): Primary Form
            with ui.column().classes("w-full lg:w-7/12 gap-6"):
                with ui.card().classes("w-full p-8 editorial-card"):
                    ui.label("Pedagogical Configuration").classes("text-2xl font-bold text-[#0B132B] mb-1")
                    ui.label("Specify subject parameters and learning goals below:").classes("text-xs text-slate-500 mb-6")

                    # Form fields
                    topic_input = ui.input(
                        label="Educational Topic *",
                        placeholder="e.g. Distributed Hash Tables (DHT)",
                    ).classes("w-full mb-4").props("outlined bg-color=white")

                    with ui.row().classes("w-full gap-4 mb-4"):
                        level_select = ui.select(
                            options=["beginner", "intermediate", "advanced"],
                            value="beginner",
                            label="Learner Expertise *",
                        ).classes("w-1/2").props("outlined bg-color=white")

                        length_select = ui.select(
                            options=["short", "medium", "long"],
                            value="medium",
                            label="Target Depth *",
                        ).classes("w-1/2").props("outlined bg-color=white")

                    objectives_input = ui.textarea(
                        label="Target Learning Objectives (one per line) *",
                        placeholder="1. Understand key definitions\n2. Walk through concrete examples\n3. Identify common misconceptions",
                        value="Understand foundational mechanisms and definitions\nDistinguish key trade-offs and real-world applications\nWalk through a complete worked example",
                    ).classes("w-full mb-6").props("outlined rows=5 bg-color=white")

                    # Submit action
                    status_label = ui.label("").classes("text-xs font-semibold text-[#0B132B] mb-2")

                    def on_submit() -> None:
                        topic = topic_input.value.strip()
                        if not topic:
                            ui.notify("Please specify an educational topic.", type="negative")
                            return

                        raw_objs = objectives_input.value.split("\n")
                        objectives = [o.strip() for o in raw_objs if o.strip()]
                        if not objectives:
                            ui.notify("At least one learning objective is required.", type="negative")
                            return

                        status_label.set_text("Dispatching request to agentic state machine...")
                        try:
                            res = client.generate_lesson(
                                topic=topic,
                                learner_level=level_select.value,
                                objectives=objectives,
                                target_length=length_select.value,
                                max_retries=int(retries_slider.value),
                                reference_documents=uploaded_reference if uploaded_reference else None,
                            )
                            run_id = res["run_id"]
                            ui.notify("Lesson synthesis started! Redirecting to live inspection...", type="positive")
                            ui.navigate.to(f"/runs/{run_id}")
                        except ApiClientError as exc:
                            status_label.set_text(f"Submission failed: {exc}")
                            ui.notify(str(exc), type="negative")

                    ui.button("Synthesize Lesson Now", on_click=on_submit).classes("w-full py-4 gold-btn shadow-md text-base")

            # Right Column (5/12 width on desktop): Controls, Budget & References
            with ui.column().classes("w-full lg:w-5/12 gap-6"):
                # Self-Correction Control Card
                with ui.card().classes("w-full p-6 editorial-card"):
                    with ui.row().classes("items-center justify-between w-full mb-2"):
                        ui.label("Automated Self-Correction Limit").classes("text-xs font-bold text-[#0B132B] uppercase tracking-wider")
                        retries_badge = ui.badge("1 Revision Retry", color="primary").classes("bg-[#0B132B] text-[#F3E5AB] px-3 py-1 text-xs font-bold")

                    retries_slider = ui.slider(min=0, max=2, step=1, value=1).classes("w-full")
                    retries_slider.on_value_change(lambda e: retries_badge.set_text(f"{int(e.value)} Revision Retries (Cap: 2)"))
                    ui.label("If blocking rubric criteria fail, the system automatically reformulates and revises the content.").classes("text-xs text-slate-500 mt-2")

                # Token Budget Notice
                with ui.card().classes("w-full p-6 bg-[#1C2541] text-white rounded-2xl shadow-sm border border-slate-700"):
                    with ui.row().classes("items-center gap-3 mb-2"):
                        ui.icon("savings", size="md").classes("text-[#DFB15B]")
                        ui.label("Zero-Token Optimization Active").classes("text-sm font-bold text-[#F3E5AB] uppercase tracking-wide")
                    ui.label(
                        "7 deterministic checks (schema integrity, word bounds, readability grade, syntax parsing, jargon definitions, citation grounding) "
                        "execute first at zero token cost. Skipping the judge on failure saves ~2,000 tokens per revision."
                    ).classes("text-xs text-slate-300 leading-relaxed")

                # File Upload Card
                with ui.card().classes("w-full p-6 editorial-card"):
                    ui.label("Optional Grounding Reference").classes("text-xs font-bold text-[#0B132B] uppercase tracking-wider mb-1")
                    ui.label("Upload reference documentation (.txt, .md only, max 200 KB) to anchor citations:").classes("text-xs text-slate-500 mb-3")

                    def handle_upload(e: Any) -> None:
                        fname = e.name
                        content = e.content.read().decode("utf-8", errors="replace")
                        uploaded_reference[fname] = content
                        ui.notify(f"Loaded reference: {fname} ({len(content)} characters)", type="positive")

                    ui.upload(
                        on_upload=handle_upload,
                        max_file_size=200_000,
                        auto_upload=True,
                    ).props('accept=".txt,.md"').classes("w-full")

                render_disclaimers()


# ==========================================
# Page: Run Inspection (/runs/{run_id})
# ==========================================

@ui.page("/runs/{run_id}")
def run_page(run_id: str) -> None:
    """Renders the real-time execution, rubric inspection, and lesson preview page.

    Args:
        run_id: Unique generation run identifier.

    Returns:
        None
    """
    render_header()

    with ui.column().classes("w-full max-w-[1500px] mx-auto px-6 lg:px-12 py-8 gap-6"):
        render_disclaimers()

        # Run Header Info Card
        header_card = ui.card().classes("w-full p-6 editorial-card")
        with header_card:
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-1"):
                    ui.label(f"Execution Run: {run_id}").classes("font-editorial text-2xl font-bold text-[#0B132B]")
                    topic_label = ui.label("Querying execution state...").classes("text-sm text-slate-500")
                with ui.row().classes("items-center gap-3"):
                    status_badge = ui.badge("INITIALIZING").classes("px-4 py-2 font-bold text-xs uppercase tracking-wider rounded-full bg-[#1C2541] text-[#F3E5AB]")
                    cancel_btn = ui.button("Cancel Execution").props("outline color=red size=sm")

        # Container for main interactive run content
        content_container = ui.column().classes("w-full gap-6")

        def handle_cancel() -> None:
            try:
                client.cancel_run(run_id)
                ui.notify("Cancellation signal transmitted.", type="warning")
            except ApiClientError as err:
                ui.notify(f"Cancellation error: {err}", type="negative")

        cancel_btn.on_click(handle_cancel)

        # Polling state refresher
        def poll_run_state() -> None:
            try:
                data = client.get_run(run_id)
                topic_label.set_text(f"Subject: {data.get('topic', 'N/A')}  |  Target Audience: {data.get('learner_level', 'N/A').upper()}  |  Depth: {data.get('target_length', 'N/A').upper()}")
                st = data.get("status", "UNKNOWN")

                badge_style = "background-color: #1C2541; color: #F3E5AB;"
                if st == "PASS":
                    badge_style = "background-color: #065F46; color: #D1FAE5;"
                    cancel_btn.set_visibility(False)
                elif st in {"REJECTED", "ERROR"}:
                    badge_style = "background-color: #991B1B; color: #FEE2E2;"
                    cancel_btn.set_visibility(False)
                elif st == "CANCELLED":
                    badge_style = "background-color: #9A3412; color: #FFEDD5;"
                    cancel_btn.set_visibility(False)
                elif st == "RUNNING":
                    badge_style = "background-color: #C5A059; color: #0B132B;"

                status_badge.set_text(st)
                status_badge.style(badge_style)

                # Populate content container when finished or updated
                content_container.clear()
                with content_container:
                    # Tabs with luxury styling
                    with ui.tabs().classes("w-full border-b border-[#E8DFD1] text-[#0B132B]") as tabs:
                        tab_lesson = ui.tab("Synthesized Lesson").classes("font-semibold")
                        tab_rubric = ui.tab("Rubric Audit (13 Criteria)").classes("font-semibold")
                        tab_claims = ui.tab("Grounded Claims").classes("font-semibold")
                        tab_rejections = ui.tab("Self-Correction Rejection Log").classes("font-semibold")
                        tab_feedback = ui.tab("Review & Feedback").classes("font-semibold")

                    with ui.tab_panels(tabs, value=tab_lesson).classes("w-full p-4 bg-transparent"):
                        # Panel 1: Lesson Content
                        with ui.tab_panel(tab_lesson):
                            final_lesson = data.get("final_lesson")
                            if final_lesson:
                                with ui.card().classes("w-full p-8 editorial-card"):
                                    ui.label(final_lesson.get("title", "Untitled Lesson")).classes("font-editorial text-3xl font-bold text-[#0B132B] mb-3")
                                    ui.markdown(final_lesson.get("introduction", "")).classes("text-slate-700 leading-relaxed text-base mb-6")

                                    ui.label("Core Definition").classes("text-lg font-bold text-[#0B132B] border-b pb-1 mb-2")
                                    ui.markdown(final_lesson.get("definition", "")).classes("text-slate-700 mb-6")

                                    ui.label("Why It Matters").classes("text-lg font-bold text-[#0B132B] border-b pb-1 mb-2")
                                    ui.markdown(final_lesson.get("why_it_matters", "")).classes("text-slate-700 mb-6")

                                    ui.label("Instructional Steps").classes("text-lg font-bold text-[#0B132B] border-b pb-1 mb-3")
                                    for idx, s in enumerate(final_lesson.get("steps", []), 1):
                                        with ui.card().classes("w-full p-4 mb-3 rounded-xl border border-[#E8DFD1] bg-[#FAF7F2]"):
                                            ui.label(f"{s.get('heading', f'Step {idx}')}").classes("font-bold text-[#0B132B] text-base mb-1")
                                            ui.markdown(s.get("body", "")).classes("text-slate-700 text-sm")

                                    we = final_lesson.get("worked_example", {})
                                    ui.label("Worked Demonstration").classes("text-lg font-bold text-[#0B132B] border-b pb-1 mb-3 mt-4")
                                    with ui.column().classes("w-full worked-example-box mb-6"):
                                        ui.label("SCENARIO").classes("text-xs font-bold text-[#9A7B38] tracking-widest uppercase")
                                        ui.markdown(we.get("scenario", "")).classes("text-slate-800 font-medium mb-3")
                                        ui.label("STEP-BY-STEP WALKTHROUGH").classes("text-xs font-bold text-[#9A7B38] tracking-widest uppercase")
                                        ui.markdown(we.get("walkthrough", "")).classes("text-slate-800")

                                    ui.label("Summary & Key Takeaways").classes("text-lg font-bold text-[#0B132B] border-b pb-1 mb-3")
                                    ui.markdown(final_lesson.get("summary", "")).classes("text-slate-700 mb-3")
                                    for t in final_lesson.get("takeaways", []):
                                        ui.label(f"• {t}").classes("text-sm text-slate-700 mb-1")

                                    # Raw Export Button
                                    with ui.row().classes("w-full justify-end mt-6 pt-4 border-t border-[#E8DFD1]"):
                                        lesson_json = json.dumps(final_lesson, indent=2)
                                        ui.download(content=lesson_json.encode("utf-8"), filename=f"lesson_{run_id}.json").classes("navy-btn px-6 py-2 shadow")
                            else:
                                if st == "RUNNING":
                                    with ui.column().classes("w-full py-16 items-center justify-center gap-4"):
                                        ui.spinner(size="xl", color="primary").classes("text-[#C5A059]")
                                        ui.label("Autonomous synthesis and multi-stage evaluation in progress...").classes("text-sm font-semibold text-[#0B132B]")
                                else:
                                    ui.label("No finalized lesson available for this execution.").classes("text-slate-400 italic")

                        # Panel 2: Rubric Evaluation
                        with ui.tab_panel(tab_rubric):
                            evals = data.get("evaluations", [])
                            if evals:
                                latest_eval = evals[-1]
                                criteria = latest_eval.get("criterion_results", [])

                                with ui.card().classes("w-full p-6 editorial-card"):
                                    with ui.row().classes("w-full justify-between items-center mb-4"):
                                        ui.label("13-Criterion Pass/Fail Rubric Audit").classes("text-lg font-bold text-[#0B132B]")
                                        severity_filter = ui.select(
                                            options=["All", "critical", "major", "minor"],
                                            value="All",
                                            label="Filter Severity",
                                        ).classes("w-44").props("outlined dense bg-color=white")

                                    table_container = ui.column().classes("w-full")

                                    def update_rubric_table(val: str) -> None:
                                        table_container.clear()
                                        filtered = criteria if val == "All" else [c for c in criteria if c.get("severity") == val]
                                        columns = [
                                            {"name": "id", "label": "Rubric Criterion", "field": "criterion_id", "align": "left"},
                                            {"name": "severity", "label": "Severity", "field": "severity", "align": "center"},
                                            {"name": "status", "label": "Verdict", "field": "status", "align": "center"},
                                            {"name": "reason", "label": "Evidence & Audit Rationale", "field": "reason", "align": "left"},
                                        ]
                                        rows = [
                                            {
                                                "criterion_id": c.get("criterion_id"),
                                                "severity": c.get("severity"),
                                                "status": c.get("status"),
                                                "reason": c.get("reason"),
                                            }
                                            for c in filtered
                                        ]
                                        with table_container:
                                            ui.table(columns=columns, rows=rows, row_key="criterion_id").classes("w-full")

                                    severity_filter.on_value_change(lambda e: update_rubric_table(e.value))
                                    update_rubric_table("All")
                            else:
                                ui.label("No evaluation records compiled yet.").classes("text-slate-400 italic")

                        # Panel 3: Claims List
                        with ui.tab_panel(tab_claims):
                            evals = data.get("evaluations", [])
                            if evals and evals[-1].get("claims"):
                                claims = evals[-1].get("claims", [])
                                with ui.card().classes("w-full p-6 editorial-card"):
                                    ui.label("Factual Claim Extraction & Grounding").classes("text-lg font-bold text-[#0B132B] mb-4")
                                    for c in claims:
                                        with ui.card().classes("w-full p-4 mb-3 rounded-xl border border-[#E8DFD1] bg-[#FAF7F2]"):
                                            with ui.row().classes("justify-between items-center w-full"):
                                                ui.label(c.get("text", "")).classes("font-semibold text-slate-800")
                                                c_status = c.get("status", "UNVERIFIABLE")
                                                badge_bg = "#065F46" if c_status == "SUPPORTED" else "#475569"
                                                ui.badge(c_status).style(f"background-color: {badge_bg}; color: white; padding: 4px 8px;")
                                            if c.get("source_id"):
                                                ui.label(f"Cited Source: {c.get('source_id')} | Direct Quote: \"{c.get('evidence_quote', '')}\"").classes("text-xs text-[#C5A059] font-medium mt-1")
                            else:
                                ui.label("No atomic claims extracted for this iteration.").classes("text-slate-400 italic")

                        # Panel 4: Rejection Audit Log
                        with ui.tab_panel(tab_rejections):
                            rejections = data.get("rejection_logs", [])
                            if rejections:
                                for r in rejections:
                                    with ui.card().classes("w-full p-6 mb-4 rounded-xl border border-red-300 bg-red-50/70"):
                                        with ui.row().classes("justify-between items-center mb-2"):
                                            ui.label(f"Revision Cycle (Attempt {r.get('attempt')})").classes("font-bold text-red-950 text-base")
                                            ui.badge(r.get("result")).classes("bg-red-800 text-white px-3 py-1")
                                        ui.label(f"Deficiencies Flagged: {', '.join(r.get('failed_criteria', []))}").classes("text-sm font-semibold text-red-900")
                                        ui.label(f"Audit Rationale: {'; '.join(r.get('reasons', []))}").classes("text-xs text-red-800 mt-1 leading-relaxed")
                                        if r.get("changes_made"):
                                            ui.label(f"Applied Corrections: {', '.join(r.get('changes_made', []))}").classes("text-xs text-slate-700 mt-2 font-medium")
                            else:
                                with ui.card().classes("w-full p-6 editorial-card bg-emerald-50/50 border-emerald-200"):
                                    with ui.row().classes("items-center gap-3"):
                                        ui.icon("check_circle", size="md").classes("text-emerald-600")
                                        with ui.column().classes("gap-0"):
                                            ui.label("First-Attempt Approval").classes("font-bold text-emerald-900 text-base")
                                            ui.label("Zero blocking criteria failed. Content approved directly without retries.").classes("text-xs text-emerald-700")

                        # Panel 5: User Feedback Form
                        with ui.tab_panel(tab_feedback):
                            with ui.card().classes("w-full max-w-xl p-6 editorial-card"):
                                ui.label("Evaluate Generation Quality").classes("font-editorial text-xl font-bold text-[#0B132B]")
                                ui.label("Help tune future prompt generations by providing quality ratings:").classes("text-xs text-slate-500 mb-4")

                                rating_slider = ui.slider(min=1, max=5, step=1, value=5).classes("w-full mb-1")
                                ui.label().bind_text_from(rating_slider, "value", lambda v: f"Rating Score: {'★' * int(v)}{'☆' * (5 - int(v))} ({v} / 5)").classes("text-xs font-bold text-[#C5A059] mb-4")

                                with ui.column().classes("gap-2 mb-4"):
                                    tag_clarity = ui.checkbox("Clear Pedagogical Tone")
                                    tag_pedagogy = ui.checkbox("Appropriate Learner Level")
                                    tag_factual = ui.checkbox("Sound Factual Structure")

                                feedback_comment = ui.textarea(label="Detailed Critique (Optional)", placeholder="Share any specific observations...").classes("w-full mb-4").props("outlined rows=3 bg-color=white")

                                def submit_fb() -> None:
                                    tags = []
                                    if tag_clarity.value:
                                        tags.append("clear_tone")
                                    if tag_pedagogy.value:
                                        tags.append("appropriate_level")
                                    if tag_factual.value:
                                        tags.append("sound_structure")
                                    try:
                                        client.submit_feedback(
                                            run_id=run_id,
                                            rating=int(rating_slider.value),
                                            issue_tags=tags,
                                            comment=feedback_comment.value,
                                        )
                                        ui.notify("Evaluation feedback recorded. Thank you!", type="positive")
                                    except ApiClientError as err:
                                        ui.notify(f"Feedback error: {err}", type="negative")

                                ui.button("Submit Evaluation", on_click=submit_fb).classes("navy-btn py-2 px-6")

                # Deactivate timer if finished
                if st in {"PASS", "REJECTED", "ERROR", "CANCELLED", "BUDGET_EXHAUSTED"}:
                    timer.deactivate()

            except ApiClientError as exc:
                topic_label.set_text(f"API Error: {exc}")

        # Start timer polling every 1.5s
        timer = ui.timer(1.5, poll_run_state)
        # Immediate first execution
        poll_run_state()


# ==========================================
# Page: History (/history)
# ==========================================

@ui.page("/history")
def history_page() -> None:
    """Renders the historical runs table with expanded desktop layout.

    Returns:
        None
    """
    render_header()

    with ui.column().classes("w-full max-w-[1500px] mx-auto px-6 lg:px-12 py-8 gap-6"):
        with ui.row().classes("w-full justify-between items-center"):
            with ui.column().classes("gap-1"):
                ui.label("Execution Archive").classes("font-editorial text-3xl font-bold text-[#0B132B]")
                ui.label("Chronological log of past lesson synthesis runs and outcomes.").classes("text-xs text-slate-500")

        runs_container = ui.column().classes("w-full")
        try:
            runs = client.get_runs()
            if not runs:
                with ui.card().classes("w-full p-12 editorial-card items-center text-center"):
                    ui.icon("inventory_2", size="xl").classes("text-[#C5A059] mb-3")
                    ui.label("No historical runs recorded yet.").classes("text-slate-500 font-semibold text-base")
                    ui.link("Synthesize your first lesson →", "/").classes("text-[#C5A059] font-bold mt-2 hover:underline")
            else:
                columns = [
                    {"name": "id", "label": "Run Identifier", "field": "id", "align": "left"},
                    {"name": "topic", "label": "Educational Subject", "field": "topic", "align": "left"},
                    {"name": "level", "label": "Audience Level", "field": "learner_level", "align": "center"},
                    {"name": "status", "label": "Status", "field": "status", "align": "center"},
                    {"name": "created", "label": "Timestamp", "field": "created_at", "align": "left"},
                ]
                with runs_container:
                    with ui.card().classes("w-full p-6 editorial-card"):
                        table = ui.table(columns=columns, rows=runs, row_key="id").classes("w-full")
                        table.add_slot(
                            "body-cell-id",
                            r"""
                            <q-td :props="props">
                                <a :href="'/runs/' + props.row.id" class="text-[#C5A059] font-mono font-bold hover:underline">
                                    {{ props.row.id.substring(0, 8) }}...
                                </a>
                            </q-td>
                            """,
                        )
        except ApiClientError as exc:
            ui.label(f"Failed to load run archive: {exc}").classes("text-red-600")


# ==========================================
# Page: Metrics (/metrics)
# ==========================================

@ui.page("/metrics")
def metrics_page() -> None:
    """Renders operational, quality, and token efficiency metrics with expanded desktop layout.

    Returns:
        None
    """
    render_header()

    with ui.column().classes("w-full max-w-[1500px] mx-auto px-6 lg:px-12 py-8 gap-6"):
        with ui.column().classes("gap-1"):
            ui.label("Quality & Efficiency Dashboard").classes("font-editorial text-3xl font-bold text-[#0B132B]")
            ui.label("Empirical telemetry auditing release rates, retry distributions, and token expenditures.").classes("text-xs text-slate-500")

        try:
            m = client.get_metrics()

            # KPI Grid: 4 Equal Expansive Columns
            with ui.row().classes("w-full gap-6"):
                with ui.card().classes("flex-1 p-6 editorial-card"):
                    ui.label("TOTAL SYNTHESES").classes("text-xs font-bold text-slate-400 tracking-wider")
                    ui.label(str(m.get("total_runs", 0))).classes("text-4xl font-extrabold text-[#0B132B] mt-2")

                with ui.card().classes("flex-1 p-6 editorial-card"):
                    ui.label("OVERALL PASS RATE").classes("text-xs font-bold text-slate-400 tracking-wider")
                    pass_rate = m.get("overall_pass_rate", 0.0)
                    ui.label(f"{pass_rate * 100:.1f}%").classes("text-4xl font-extrabold text-[#065F46] mt-2")

                with ui.card().classes("flex-1 p-6 editorial-card"):
                    ui.label("1ST ATTEMPT PASS RATE").classes("text-xs font-bold text-slate-400 tracking-wider")
                    first_rate = m.get("first_attempt_pass_rate", 0.0)
                    ui.label(f"{first_rate * 100:.1f}%").classes("text-4xl font-extrabold text-[#C5A059] mt-2")

                with ui.card().classes("flex-1 p-6 editorial-card"):
                    ui.label("MEAN TOKENS / RUN").classes("text-xs font-bold text-slate-400 tracking-wider")
                    avg_tok = m.get("avg_tokens_per_run", 0.0)
                    ui.label(f"{avg_tok:,.0f}").classes("text-4xl font-extrabold text-[#1C2541] mt-2")

            # Detailed Analytics Cards: 2 Columns
            with ui.row().classes("w-full gap-6 mt-2"):
                with ui.card().classes("flex-1 p-8 editorial-card"):
                    ui.label("Retry Cycle Distribution").classes("text-xl font-bold text-[#0B132B] mb-4 border-b pb-2")
                    dist = m.get("retry_distribution", {})
                    ui.label(f"• Direct Approval (0 Retries): {dist.get('0_retries', 0)}").classes("text-sm text-slate-700 mb-2")
                    ui.label(f"• Corrected on 1st Retry: {dist.get('1_retry', 0)}").classes("text-sm text-slate-700 mb-2")
                    ui.label(f"• Reached Maximum Cap (2 Retries): {dist.get('2_retries', 0)}").classes("text-sm text-slate-700")

                with ui.card().classes("flex-1 p-8 editorial-card"):
                    ui.label("Level A Pitfall Hint Impact").classes("text-xl font-bold text-[#0B132B] mb-4 border-b pb-2")
                    p_with = m.get("pass_rate_with_hint")
                    p_without = m.get("pass_rate_without_hint")
                    val_with = f"{p_with * 100:.1f}%" if p_with is not None else "Insufficient historical data"
                    val_without = f"{p_without * 100:.1f}%" if p_without is not None else "Insufficient historical data"
                    ui.label(f"• Release Rate WITH Pitfall Guidance: {val_with}").classes("text-sm text-slate-700 mb-2")
                    ui.label(f"• Release Rate WITHOUT Pitfall Guidance: {val_without}").classes("text-sm text-slate-700 mb-3")
                    ui.label("Pitfall hints are aggregated strictly from static templates keyed by criterion ID (cap 150 tokens).").classes("text-xs text-slate-400 italic")

        except ApiClientError as exc:
            ui.label(f"Failed to load metrics: {exc}").classes("text-red-600")


if __name__ in {"__main__", "__mp_main__"}:
    port = int(os.getenv("UI_PORT", "8080"))
    ui.run(port=port, title="Learn Loop | Autonomous Lesson Generator", reload=False)
