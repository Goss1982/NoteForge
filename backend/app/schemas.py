from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Block(StrictModel):
    kind: Literal["text", "list", "table", "diagram", "annotation"]
    text: str
    evidence_quote: str
    confidence: float = Field(ge=0, le=1)
    uncertain: bool


class Insight(StrictModel):
    kind: Literal["action", "decision", "question", "date", "responsibility"]
    text: str
    evidence_quote: str
    owner: str | None
    due_date: str | None
    confidence: float = Field(ge=0, le=1)


class Extraction(StrictModel):
    transcript: str
    category: Literal["Meeting", "Planning", "Research", "Ideas", "Personal", "Other"]
    purpose: str
    blocks: list[Block]
    insights: list[Insight]
    uncertainties: list[str]


class Citation(StrictModel):
    page_id: str
    quote: str = Field(min_length=1)


class Paragraph(StrictModel):
    kind: Literal["fact", "interpretation", "recommendation"]
    text: str = Field(min_length=1, max_length=20000)
    citations: list[Citation]


class Section(StrictModel):
    heading: str = Field(min_length=1, max_length=200)
    paragraphs: list[Paragraph]


class DocumentContent(StrictModel):
    title: str = Field(min_length=1, max_length=500)
    sections: list[Section] = Field(min_length=1, max_length=30)
    missing_information: list[str]


class GenerateRequest(BaseModel):
    kind: Literal["meeting_minutes", "brief", "report", "action_plan"] = "meeting_minutes"


class EditDocument(BaseModel):
    expected_version: int = Field(ge=1)
    content: DocumentContent
    reviewed: bool = False


class PageReview(BaseModel):
    status: Literal["unreviewed", "verified", "needs_correction"]
    note: str = Field(default="", max_length=5000)
