"""One shape for every API error: {"error": {"code": ..., "message": ...}} (API_CONTRACT.md).

Owner: Mit.
"""

from fastapi import HTTPException, status


def api_error(code: int, error: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": error, "message": message}})


def not_found(what: str) -> HTTPException:
    """404 for anything that does not exist *or belongs to someone else*: never confirm that
    another learner's id is valid."""
    return api_error(
        status.HTTP_404_NOT_FOUND, f"{what.upper()}_NOT_FOUND", f"{what.capitalize()} not found"
    )
