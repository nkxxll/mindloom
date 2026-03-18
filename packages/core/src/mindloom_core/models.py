from __future__ import annotations

from datetime import datetime
from enum import Enum, StrEnum, auto
from typing import Optional

from pydantic import BaseModel


class SectionRequest(BaseModel):
    start: int
    end: int
    content: str
    file_path: str
    model: Optional[Model] = None


class Status(StrEnum):
    # Common statuses: "pending", "running", "completed", "failed", "waiting_for"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR = "waiting_for"


class Job(BaseModel):
    id: int
    task_type: str
    content: Optional[str]
    result: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    dependencies: Optional[str] = None


class JobCreate(BaseModel):
    task_type: EthemeralTaskType | ConversationTaskType
    content: str
    dependencies: Optional[str] = None


class JobResponse(BaseModel):
    id: int
    task_type: str
    content: Optional[str]
    result: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    dependencies: Optional[str] = None


class SectionResponse(BaseModel):
    content: str
    length: int


class FileRequest(BaseModel):
    content: str
    file_path: str
    model: Optional[Model] = None


class EmailRequest(BaseModel):
    content: str
    model: Optional[Model] = None


class SummarizeRequest(BaseModel):
    content: str
    max_length: Optional[int] = None
    model: Optional[Model] = None


class TranslateRequest(BaseModel):
    content: str
    target_language: str
    source_language: Optional[str] = None
    model: Optional[Model] = None


class ExplainCodeRequest(BaseModel):
    content: str
    language: Optional[str] = None
    model: Optional[Model] = None


class CommitMessageRequest(BaseModel):
    content: str
    model: Optional[Model] = None


class ExtractActionsRequest(BaseModel):
    content: str
    model: Optional[Model] = None


class RewriteToneRequest(BaseModel):
    content: str
    target_tone: str
    model: Optional[Model] = None


class ProofreadRequest(BaseModel):
    content: str
    model: Optional[Model] = None


class GenerateTestsRequest(BaseModel):
    content: str
    language: Optional[str] = None
    framework: Optional[str] = None
    model: Optional[Model] = None


class AskRequest(BaseModel):
    question: str
    markdown: bool = False
    model: Optional[Model] = None


class ConversationTaskType(Enum):
    """Maybe in the future we want to have a chat with the model maybe a faster model to incremetnally improve some parts of a note or an email.

    For this we will need another API structure with message IDs and other stuff that we'll define then.
    """

    pass


class EthemeralTaskType(Enum):
    FILE = auto()
    SECTION = auto()
    SECTION_EXTEND = auto()
    IMPROVE_EMAIL = auto()
    WRITE_EMAIL = auto()
    SUMMARIZE = auto()
    TRANSLATE = auto()
    EXPLAIN_CODE = auto()
    COMMIT_MESSAGE = auto()
    EXTRACT_ACTIONS = auto()
    REWRITE_TONE = auto()
    PROOFREAD = auto()
    GENERATE_TESTS = auto()
    ASK = auto()


class Model(StrEnum):
    MINISTRAL = "ministral-3:latest"
    QWEN = "qwen3:latest"
    QWEN314 = "qwen3:14b"
    QWEN35 = "qwen3.5:latest"
    GEMMA3 = "gemma3:latest"
    LLAMA3 = "llama3.2:latest"

    @property
    def supports_thinking(self) -> bool:
        return self in {Model.QWEN, Model.QWEN314}
