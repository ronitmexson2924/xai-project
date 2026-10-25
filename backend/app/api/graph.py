"""GET /graph: the concept DAG for the learner dashboard. Owner: Mit."""

from fastapi import APIRouter

from app.api.deps import Graph
from app.api.schemas import GraphResponse
from app.auth import CurrentUser

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphResponse, summary="The concept graph and its prerequisites")
def get_graph(_: CurrentUser, graph: Graph) -> GraphResponse:
    concepts, edges = graph.get_graph()
    return GraphResponse(concepts=concepts, edges=edges)
