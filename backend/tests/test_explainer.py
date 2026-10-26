"""Unit tests for Grounded Explainer (M3).

Owner: Mit.
Verifies:
- Mocked Gemini client (valid structured output -> source='llm')
- Mocked Gemini invalid concept ID -> validator catches hallucination -> template fallback
- Mocked Gemini timeout -> template fallback (source='template')
- Precompute run for 3 concepts produces 36 rows
- Runtime latency p95 < 50ms when precomputed variant exists
- Grounding validator logic (word counts, disallowed concepts, code block restrictions)
- Explanation wrapper (reasons, tone, mermaid diagrams)
"""

import json
import time
from uuid import uuid4

from app.contracts.explanation import ExplanationRequest, StyleParams
from app.contracts.graph import Concept, ConceptCard
from app.contracts.reasons import ReasonCode, ReasonEvidence
from app.explainer.llm import LLMClientProtocol
from app.explainer.precompute import get_all_variant_styles, precompute_all
from app.explainer.prompt import PROMPT_VERSION, card_has_code
from app.explainer.service import GroundedExplainerService
from app.explainer.store import ExplanationVariantRecord, VariantStore
from app.explainer.templates import render_template_fallback
from app.explainer.validator import validate_explanation
from app.explainer.wrapper import wrap_explanation


class MockGeminiClient(LLMClientProtocol):
    """Configurable mock for Gemini GenAI client."""

    def __init__(
        self,
        mode: str = "valid",
        body_text: str | None = None,
        concept_ids: list[str] | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.mode = mode
        self.body_text = body_text
        self.concept_ids = concept_ids
        self.delay_seconds = delay_seconds
        self.call_count = 0

    def generate(self, model: str, prompt: str, timeout: float) -> str:
        self.call_count += 1
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        if self.mode == "timeout":
            raise TimeoutError("Gemini call timed out after 4.0s")
        elif self.mode == "invalid_json":
            return "This is not valid JSON at all."
        elif self.mode == "hallucination":
            # Mentions a concept not permitted in request
            payload = {
                "body_markdown": "Binary search divides the interval into halves.",
                "concept_ids_mentioned": ["binary-search-bounds", "unrelated-concept"],
            }
            return json.dumps(payload)
        elif self.mode == "valid":
            target_concept = "loops"
            for line in prompt.splitlines():
                if line.startswith("Target Concept ID:"):
                    target_concept = line.split(":", 1)[1].strip()
                    break
            payload = {
                "body_markdown": (
                    self.body_text
                    or f"A verified explanation for {target_concept} grounded in the card."
                ),
                "concept_ids_mentioned": self.concept_ids or [target_concept],
            }
            return json.dumps(payload)
        else:
            raise ValueError(f"Unknown mock mode: {self.mode}")


class FakeThreeConceptGraph:
    """Graph service containing 3 DSA concepts for testing precompute and explanations."""

    def __init__(self) -> None:
        self.concepts = {
            "loops": Concept(
                id="loops",
                name="Loops",
                cluster="basics",
                description="Repeating a block of code.",
                difficulty=1,
                card=ConceptCard(
                    definition="A loop runs a block of code repeatedly while a condition holds.",
                    key_idea="Every loop needs a condition that eventually becomes false.",
                    worked_example="for i in range(3): print(i)  # prints 0, 1, 2",
                    pitfall="Off-by-one: range(3) stops before 3.",
                ),
            ),
            "recursion-base-case": Concept(
                id="recursion-base-case",
                name="Recursion: base case",
                cluster="recursion",
                description="The stopping condition of a recursive function.",
                difficulty=2,
                card=ConceptCard(
                    definition=(
                        "A base case is an input a recursive function answers without recursing."
                    ),
                    key_idea="Each recursive call must move closer to a base case.",
                    worked_example="def fact(n): return 1 if n == 0 else n * fact(n - 1)",
                    pitfall="A missing or unreachable base case causes infinite recursion.",
                ),
            ),
            "binary-search-bounds": Concept(
                id="binary-search-bounds",
                name="Binary Search Bounds",
                cluster="searching",
                description="Maintaining bounds in binary search.",
                difficulty=3,
                card=ConceptCard(
                    definition=(
                        "Binary search maintains low and high pointers enclosing the space."
                    ),
                    key_idea="Update low = mid + 1 or high = mid - 1 to guarantee progress.",
                    worked_example="while low <= high: mid = (low + high) // 2",
                    pitfall="Using high = mid can cause an infinite loop.",
                    diagram="graph LR\n  A[low] --> B[mid]\n  B --> C[high]",
                ),
            ),
        }

    def get_concept(self, concept_id: str) -> Concept:
        if concept_id not in self.concepts:
            raise KeyError(concept_id)
        return self.concepts[concept_id]

    def get_graph(self) -> tuple[list[Concept], list]:
        return list(self.concepts.values()), []


def _make_explanation_request(
    concept_id: str = "loops",
    style: StyleParams | None = None,
    reasons: list[ReasonEvidence] | None = None,
) -> ExplanationRequest:
    return ExplanationRequest(
        recommendation_id=uuid4(),
        user_id=uuid4(),
        concept_ids=[concept_id],
        style=style or StyleParams(example_first=False, length="short", depth="how"),
        style_source="thompson",
        reasons=reasons
        or [
            ReasonEvidence(
                code=ReasonCode.PREREQ_GAP,
                concept_id=concept_id,
                value=0.35,
            )
        ],
    )


# -----------------------------------------------------------------------------
# Acceptance Criteria 1: Mock Gemini Tests
# -----------------------------------------------------------------------------


def test_explainer_valid_mock_gemini_returns_llm_source():
    """Valid structured output passes validation and is returned with source='llm'."""
    graph = FakeThreeConceptGraph()
    mock_client = MockGeminiClient(
        mode="valid",
        body_text="A loop runs code repeatedly. Make sure the condition terminates.",
        concept_ids=["loops"],
    )
    store = VariantStore()  # empty store so it doesn't hit precomputed
    service = GroundedExplainerService(graph=graph, store=store, llm_client=mock_client)

    req = _make_explanation_request(concept_id="loops")
    explanation = service.explain(req)

    assert explanation.source == "llm"
    assert explanation.model is not None
    assert "A loop runs code repeatedly." in explanation.body_markdown
    # Wrapper added reason sentence
    # learners see the concept's name, not its id
    assert "**Why this:** Strengthening prerequisite knowledge for Loops" in (
        explanation.body_markdown
    )
    assert mock_client.call_count == 1


def test_explainer_hallucination_triggers_template_fallback():
    """Mock Gemini returning an unallowed concept ID triggers the fallback."""
    graph = FakeThreeConceptGraph()
    mock_client = MockGeminiClient(mode="hallucination")  # returns 'unrelated-concept'
    store = VariantStore()
    service = GroundedExplainerService(graph=graph, store=store, llm_client=mock_client)

    req = _make_explanation_request(concept_id="loops")
    explanation = service.explain(req)

    assert explanation.source == "template"
    assert explanation.model is None
    # Template fallback was used:
    assert "A loop runs a block of code repeatedly while a condition holds." in (
        explanation.body_markdown
    )
    assert "**Why this:**" in explanation.body_markdown


def test_explainer_timeout_triggers_template_fallback():
    """Mock Gemini timing out (> 4s or TimeoutError) triggers the fallback."""
    graph = FakeThreeConceptGraph()
    mock_client = MockGeminiClient(mode="timeout")
    store = VariantStore()
    service = GroundedExplainerService(graph=graph, store=store, llm_client=mock_client)

    req = _make_explanation_request(concept_id="recursion-base-case")
    explanation = service.explain(req)

    assert explanation.source == "template"
    assert explanation.model is None
    assert "A base case is an input a recursive function answers without recursing." in (
        explanation.body_markdown
    )


# -----------------------------------------------------------------------------
# Acceptance Criteria 2: Precompute 3 Concepts Produces 36 Rows
# -----------------------------------------------------------------------------


def test_precompute_3_concepts_produces_36_rows():
    """Precomputing 12 variants for 3 concepts yields exactly 36 valid rows."""
    graph = FakeThreeConceptGraph()
    concepts, _ = graph.get_graph()
    assert len(concepts) == 3

    store = VariantStore()
    mock_client = MockGeminiClient(mode="valid")

    generated = precompute_all(concepts=concepts, store=store, client=mock_client)
    assert generated == 36
    assert store.count() == 36

    # Verify each concept has all 12 combinations
    expected_styles = get_all_variant_styles()
    assert len(expected_styles) == 12

    for concept in concepts:
        variants = store.list_variants_for_concept(concept.id)
        assert len(variants) == 12
        for style in expected_styles:
            rec = store.get_variant(concept.id, style.variant_key(), PROMPT_VERSION)
            assert rec is not None
            assert rec.review_status == "auto_ok"
            assert rec.validation["valid"] is True


def test_precompute_resume_support():
    """Precompute skips already computed variants unless force=True."""
    graph = FakeThreeConceptGraph()
    concepts, _ = graph.get_graph()
    store = VariantStore()

    # First run
    c1 = precompute_all(concepts=[concepts[0]], store=store)
    assert c1 == 12
    assert store.count() == 12

    # Second run without force does not re-compute
    c2 = precompute_all(concepts=[concepts[0]], store=store)
    assert c2 == 0
    assert store.count() == 12


# -----------------------------------------------------------------------------
# Acceptance Criteria 3: Latency Benchmark p95 < 50ms
# -----------------------------------------------------------------------------


def test_runtime_latency_p95_under_50ms():
    """When a precomputed variant exists, explain() p95 latency is under 50ms."""
    graph = FakeThreeConceptGraph()
    store = VariantStore()

    style = StyleParams(example_first=True, length="medium", depth="how")
    variant_record = ExplanationVariantRecord(
        concept_id="loops",
        style_key=style.variant_key(),
        body_markdown="For example: for i in range(3): print(i). Loops run repeatedly.",
        prompt_version=PROMPT_VERSION,
        model="gemini-2.5-flash",
        validation={"valid": True, "word_count": 12, "max_words": 160},
        review_status="approved",
    )
    store.put_variant(variant_record)

    service = GroundedExplainerService(graph=graph, store=store, llm_client=None)
    req = _make_explanation_request(concept_id="loops", style=style)

    # Warm-up run
    warmup = service.explain(req)
    assert warmup.source == "precomputed"

    # Measure 100 runs
    latencies: list[float] = []
    for _ in range(100):
        t0 = time.perf_counter()
        resp = service.explain(req)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)
        assert resp.source == "precomputed"

    latencies.sort()
    # 95th percentile
    p95_idx = int(0.95 * len(latencies))
    p95_latency = latencies[p95_idx]

    # Stated SLA in tasks/mit.md is p95 < 50ms
    assert p95_latency < 50.0, f"p95 latency was {p95_latency:.2f}ms >= 50ms"


# -----------------------------------------------------------------------------
# Additional Grounding, Validator, & Wrapper Tests
# -----------------------------------------------------------------------------


def test_validator_word_count_limits():
    """Validator rejects body if it exceeds word count limits."""
    card = ConceptCard(
        definition="Loop definition.",
        key_idea="Key loop idea.",
        worked_example="for x in [1, 2]: pass",
        pitfall="Off by one.",
    )

    # 10 words in body
    short_body = "word " * 10
    res_short = validate_explanation(
        body_markdown=short_body,
        concept_ids_mentioned=["loops"],
        allowed_concept_ids=["loops"],
        card=card,
        style=StyleParams(example_first=False, length="short", depth="how"),
    )
    assert res_short.valid is True

    # 85 words in body (limit for short is 80)
    over_limit_body = "word " * 85
    res_over = validate_explanation(
        body_markdown=over_limit_body,
        concept_ids_mentioned=["loops"],
        allowed_concept_ids=["loops"],
        card=card,
        style=StyleParams(example_first=False, length="short", depth="how"),
    )
    assert res_over.valid is False
    assert any("exceeds maximum 80" in err for err in res_over.errors)


def test_validator_illegal_code_blocks():
    """Validator rejects code blocks if the concept card contains no code."""
    card_without_code = ConceptCard(
        definition="Recursion is self-referential definition.",
        key_idea="Base case halts.",
        worked_example="Consider a set of Russian dolls nested inside each other.",
        pitfall="Circular definition without stopping.",
    )

    body_with_code = "Here is some code:\n```python\nprint(1)\n```"
    res = validate_explanation(
        body_markdown=body_with_code,
        concept_ids_mentioned=["recursion"],
        allowed_concept_ids=["recursion"],
        card=card_without_code,
        style=StyleParams(example_first=False, length="medium", depth="how"),
    )
    assert res.valid is False
    assert res.illegal_code_blocks is True


def test_wrapper_diagram_and_encouraging_tone():
    """Wrapper properly appends reason, encouraging tone, and mermaid diagrams."""
    card = ConceptCard(
        definition="Binary search definition.",
        key_idea="Binary search idea.",
        worked_example="low = mid + 1",
        pitfall="Bounds check.",
        diagram="graph LR\n  A --> B",
    )
    style = StyleParams(
        example_first=False,
        length="medium",
        depth="how",
        tone="encouraging",
        include_diagram=True,
    )
    reasons = [
        ReasonEvidence(
            code=ReasonCode.READY_FOR_NEXT,
            concept_id="binary-search",
        )
    ]

    wrapped = wrap_explanation(
        body="Core binary search content.",
        reasons=reasons,
        style=style,
        card=card,
    )

    assert "**Why this:** You have demonstrated readiness to advance to binary-search." in (wrapped)
    assert "Core binary search content." in wrapped
    assert "💡 *Take your time tracing each step." in wrapped
    assert "```mermaid\ngraph LR\n  A --> B\n```" in wrapped


def test_template_puts_the_worked_example_in_a_code_block():
    """Code keeps its lines and indentation: it is fenced on lines of its own, never inlined."""
    card = FakeThreeConceptGraph().get_concept("recursion-base-case").card
    for length in ("short", "medium", "long"):
        for example_first in (True, False):
            style = StyleParams(example_first=example_first, length=length, depth="how")
            body = render_template_fallback(card, style)
            code = card.worked_example.strip()
            assert f"```python\n{code}\n```" in body, (length, example_first)
            assert "\n\n```python" in body or body.startswith("```python")
            assert "```\n\n" in body or body.endswith("```")


def test_code_detection_covers_examples_without_def_or_for():
    """An example like `x = 5` is code too, so the prompt allows code and the validator keeps it."""
    card = ConceptCard(
        definition="A variable is a name bound to a value.",
        key_idea="Assignment binds a name.",
        worked_example="x = 5\nprint(x)",
        pitfall="Reading = as equality.",
    )
    assert card_has_code(card)
    style = StyleParams(example_first=True, length="medium", depth="how")
    body = render_template_fallback(card, style)
    assert validate_explanation(body, ["variables"], ["variables"], card, style).valid
    prose = card.model_copy(update={"worked_example": "Think of a label on a box."})
    assert not card_has_code(prose)
