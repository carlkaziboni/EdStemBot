"""Pydantic models mirroring EdStem's JSON API schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    name: str
    role: str = "student"  # student | staff | admin
    avatar: Optional[str] = None
    course_role: Optional[str] = None


class Comment(BaseModel):
    id: int
    thread_id: int
    user_id: Optional[int] = None
    user: Optional[User] = None
    content: str = ""
    document: Optional[str] = None  # HTML content
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def plain_text(self) -> str:
        """Strip HTML tags from content for plain-text processing."""
        import re
        return re.sub(r"<[^>]+>", " ", self.document or self.content).strip()


class Thread(BaseModel):
    id: int
    course_id: int
    title: str = ""
    type: str = "question"        # question | post | announcement
    category: Optional[str] = None
    subcategory: Optional[str] = None
    content: str = ""
    document: Optional[str] = None  # HTML content from EdStem
    user_id: Optional[int] = None
    user: Optional[User] = None
    is_answered: bool = False
    is_staff_answered: bool = False
    is_student_answered: bool = False
    is_endorsed: bool = False
    accepted_id: Optional[int] = None
    answers: list[dict[str, Any]] = Field(default_factory=list)
    is_private: bool = False
    is_anonymous: bool = False
    vote_count: int = 0
    view_count: int = 0
    comment_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def plain_text(self) -> str:
        """Strip HTML tags from document/content for LLM processing."""
        import re
        raw = self.document or self.content
        return re.sub(r"<[^>]+>", " ", raw).strip()

    @property
    def is_question(self) -> bool:
        return self.type == "question"


class Course(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    year: Optional[int | str] = None
    session: Optional[str] = None


class EdStemEvent(BaseModel):
    """Wrapper for WebSocket events received from EdStem."""
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
