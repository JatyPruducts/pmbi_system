from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import QuestionType, SurveyTemplate


class SurveyQuestionIn(BaseModel):
    id: str
    text: str
    question_type: QuestionType
    meta: dict[str, Any] = Field(default_factory=dict)


class SurveyCreate(BaseModel):
    title: str
    template: SurveyTemplate
    version: int = 1
    questions: list[SurveyQuestionIn]


class SurveyOut(BaseModel):
    id: str
    title: str
    template: str
    version: int
    questions: list[dict[str, Any]]


class SurveyResponseSubmit(BaseModel):
    survey_id: str
    version: int
    answers: dict[str, Any]


class SurveyResponseOut(BaseModel):
    id: str
    survey_id: str
    version: int
    submitted_at: datetime
    scores: dict[str, float] = Field(default_factory=dict)
