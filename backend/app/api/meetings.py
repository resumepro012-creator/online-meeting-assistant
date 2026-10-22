"""Meeting-access endpoints.

Read-only: they explain what is possible for a given meeting platform. Nothing
here joins a meeting or touches a platform's access controls.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from app.api.deps import get_current_user
from app.meeting.policy import assess_link, supported_platforms
from app.models import User
from app.schemas import MeetingPolicyOut, MessageResponse
from app.services.meeting_bot_service import meeting_bot

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/join", response_model=MessageResponse)
async def join_meeting(
    link: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """
    Triggers the Guest Bot to join the meeting.
    """
    background_tasks.add_task(meeting_bot.join_meeting, link, f"Assistant ({user.name})")
    return MessageResponse(message="Assistant Bot is joining the meeting. Please admit it from the waiting room.")


@router.get("/policy", response_model=MeetingPolicyOut)
def meeting_policy(
    link: str | None = Query(
        default=None,
        max_length=500,
        description="The meeting link the student pasted, if any.",
    ),
    _user: User = Depends(get_current_user),
) -> dict:
    """Separates *app authentication* from *authorization to join a meeting*.

    Requires a verified university account to call, which is exactly the point:
    being signed in here does not grant access to anybody's meeting.
    """
    assessed = assess_link(link)
    assessed["platforms"] = supported_platforms()
    return assessed
