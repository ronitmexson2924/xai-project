"""Uniform error responses: {"error": {"code": ..., "message": ...}} (API_CONTRACT.md)."""

from fastapi import HTTPException, status


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"error": {"code": code, "message": message}}
    )


def not_found(what: str) -> HTTPException:
    # the same answer whether the thing does not exist or belongs to someone else
    return api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", f"{what} was not found")


def conflict(code: str, message: str) -> HTTPException:
    return api_error(status.HTTP_409_CONFLICT, code, message)


def invalid(code: str, message: str) -> HTTPException:
    return api_error(422, code, message)
