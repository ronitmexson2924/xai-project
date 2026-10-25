"""Concept graph inspection routes.

Owner: Mit.
"""

from fastapi import APIRouter

from app.api.deps import GraphDep
from app.api.schemas import GraphResponse
from app.auth import UserDep

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphResponse, summary="The concept DAG and prerequisite edges")
def get_graph(_: UserDep, graph: GraphDep) -> GraphResponse:
    concepts, edges = graph.get_graph()
    return GraphResponse(concepts=concepts, edges=edges)
