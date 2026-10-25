"""GET /items/{id}: an item (without its answer) that was served to the caller, such as an
explanation's micro-check. Items are never browsable, so answers cannot be harvested in bulk.

Owner: Mit.
"""

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import or_, select

from app.api.deps import Svc
from app.api.errors import not_found
from app.api.session import public
from app.auth import ConsentedUser
from app.contracts.graph import PublicItem
from app.db import models as m

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/{item_id}", response_model=PublicItem, summary="Fetch an item served to you")
def get_item(item_id: str, user: ConsentedUser, svc: Svc) -> PublicItem:
    served = svc.session.scalar(
        select(m.ExplanationRow.id)
        .join(m.RecommendationRow, m.RecommendationRow.id == m.ExplanationRow.recommendation_id)
        .where(
            m.ExplanationRow.user_id == user.id,
            or_(
                m.ExplanationRow.followup_item_id == item_id, m.RecommendationRow.item_id == item_id
            ),
        )
        .limit(1)
    )
    if served is None:
        raise not_found("Item")
    try:
        return public(svc.graph.get_item(item_id))
    except LookupError:
        raise not_found("Item") from None


tests_router = APIRouter(prefix="/tests", tags=["items"])


@tests_router.get(
    "/{phase}",
    response_model=list[PublicItem],
    summary="The pre- or post-test items (answer each once through POST /attempts)",
)
def get_test(phase: Literal["pretest", "posttest"], _: ConsentedUser, svc: Svc) -> list[PublicItem]:
    ids = sorted(i for i in svc.graph.test_item_ids if i.startswith(f"{phase}-"))
    return [public(svc.graph.get_item(i)) for i in ids]
