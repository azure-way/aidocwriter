from __future__ import annotations

from fastapi import APIRouter, Depends

from docwriter.agents.interviewer import InterviewerAgent

from ..models import IntakeQuestion, IntakeQuestionsRequest, IntakeQuestionsResponse

router = APIRouter(prefix="/intake", tags=["intake"])


def _get_interviewer() -> InterviewerAgent:
    return InterviewerAgent()


@router.post("/questions", response_model=IntakeQuestionsResponse)
def intake_questions(
    payload: IntakeQuestionsRequest,
    interviewer: InterviewerAgent = Depends(_get_interviewer),
) -> IntakeQuestionsResponse:
    questions = interviewer.propose_questions(payload.title)
    return IntakeQuestionsResponse(
        title=payload.title,
        questions=[IntakeQuestion(**q) for q in questions],
    )
