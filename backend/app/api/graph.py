"""Concept graph inspection routes.

Owner: Mit.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import GraphDep
from app.api.schemas import GraphResponse
from app.auth import UserResponse, get_current_user

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get(
    "",
    response_model=GraphResponse,
    summary="Get entire concept DAG and prerequisite edges",
)
def get_graph(
    _: Annotated[UserResponse, Depends(get_current_user)],
    graph: GraphDep,
) -> GraphResponse:
    concepts, edges = graph.get_graph()
    return GraphResponse(concepts=concepts, edges=edges)
