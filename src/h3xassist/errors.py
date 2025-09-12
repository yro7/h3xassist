from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from uuid import UUID


class MeetingNotFoundError(HTTPException):
    """Meeting not found error."""

    def __init__(self, meeting_id: "UUID") -> None:
        super().__init__(status_code=404, detail=f"Meeting {meeting_id} not found")


class ProfileNotFoundError(HTTPException):
    """Profile not found error."""

    def __init__(self, profile_name: str) -> None:
        super().__init__(status_code=404, detail=f"Profile '{profile_name}' not found")


class ProfileExistsError(HTTPException):
    """Profile already exists error."""

    def __init__(self, profile_name: str) -> None:
        super().__init__(status_code=409, detail=f"Profile '{profile_name}' already exists")
