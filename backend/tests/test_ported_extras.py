"""Pieces ported from PR #7: precomputed variants in Postgres, CSP and shared pseudonyms."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.contracts.explanation import StyleParams
from app.explainer import DbVariantStore, ExplanationVariantRecord
from app.explainer.prompt import PROMPT_VERSION
from app.planner.style import GENERIC_STYLE
from app.pseudonyms import pseudonym
from tests.api_helpers import learner


def test_db_variant_store_round_trip_and_upsert(db: Session, bundle) -> None:
    from app.graph.seed import seed

    seed(db, bundle)
    store = DbVariantStore(db)
    record = ExplanationVariantRecord(
        concept_id="loops",
        style_key="ex-short-how",
        body_markdown="first",
        prompt_version="v1",
        model="m",
        validation={"ok": True},
    )
    store.put_variant(record)
    store.put_variant(record.model_copy(update={"id": uuid4(), "body_markdown": "second"}))
    assert store.count() == 1  # (concept, style, prompt version) is unique: an upsert
    assert store.get_variant("loops", "ex-short-how", "v1").body_markdown == "second"
    store.put_variant(
        record.model_copy(update={"id": uuid4(), "style_key": "x", "review_status": "rejected"})
    )
    assert store.get_variant("loops", "x", "v1") is None  # rejected variants are never served


def test_api_serves_a_precomputed_variant(client: TestClient, db: Session) -> None:
    who = learner(client, db, "generic")  # generic arm: a fixed, known style
    example_first, length, depth = GENERIC_STYLE
    style = StyleParams(example_first=example_first, length=length, depth=depth)
    for concept in ("loops", "variables-and-types"):
        DbVariantStore(db).put_variant(
            ExplanationVariantRecord(
                concept_id=concept,
                style_key=style.variant_key(),
                body_markdown=f"Precomputed text for {concept}.",
                prompt_version=PROMPT_VERSION,
                model="offline-model",
                validation={"ok": True},
            )
        )
    db.commit()
    explanation = who.next()["explanation"]
    assert explanation["source"] == "precomputed"
    assert "Precomputed text for" in explanation["body_markdown"]


def test_api_responses_forbid_active_content(client: TestClient) -> None:
    r = client.get("/api/v1/graph")
    assert r.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_admin_and_research_exports_share_pseudonyms() -> None:
    from analysis.export import pseudonym as research_pseudonym

    assert research_pseudonym is pseudonym
    assert pseudonym("u1", "salt-a") == pseudonym("u1", "salt-a") != pseudonym("u1", "salt-b")
    assert len(pseudonym("u1", "salt-a")) == 12
