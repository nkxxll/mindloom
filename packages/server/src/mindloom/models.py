from datetime import datetime
from enum import Enum, StrEnum, auto
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def now():
    return datetime.now()


class SectionRequest(BaseModel):
    start: int
    end: int
    content: str
    file_path: str
    model: Optional[Model]


class Status(StrEnum):
    # Common statuses: "pending", "running", "completed", "failed"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, index=True)

    # Using Text for long strings (unlimited length in SQLite)
    content = Column(Text, nullable=True)

    # Common statuses: "pending", "running", "completed", "failed"
    status = Column(String, default="pending")

    # Good practice: Track when the job was created/updated
    created_at = Column(DateTime, default=now())
    updated_at = Column(DateTime, default=now(), onupdate=now())


class JobCreate(BaseModel):
    task_type: "EthemeralTaskType | ConversationTaskType"
    content: str


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


class Model(StrEnum):
    MINISTRAL = "ministral-3:latest"
    QWEN = "qwen3:latest"
    QWEN314 = "qwen3:14b"
    GEMMA3 = "gemma3:latest"
    LLAMA3 = "llama3.2:latest"


class Prompts(BaseModel):
    # For TaskType.FILE: Fixing an entire code or text file
    fix_file: str = (
        "Review the following file for syntax errors, logical inconsistencies, "
        "and PEP8 compliance. Return the corrected file in full."
    )

    # For TaskType.SECTION: Fixing a specific snippet or paragraph
    fix_section: str = (
        "Analyze the provided text section. Correct any grammatical errors "
        "or clarity issues while maintaining the original tone."
    )

    # For TaskType.SECTION_EXTEND: Adding depth/length to a section
    extend_section: str = (
        "Elaborate on the following section by adding relevant details and "
        "examples. Ensure the flow remains natural and matches the existing style."
    )

    # For TaskType.IMPROVE_EMAIL: Refining an existing draft
    fix_email: str = (
        "Refine this email draft to be more professional and concise. "
        "Ensure the call to action is clear and the tone is polite."
    )

    # For TaskType.WRITE_EMAIL: Generating from scratch (New field)
    write_email: str = (
        "Draft a new email based on the following key points. "
        "Use a professional subject line and a structured body."
    )


def get_user_message(task_type: EthemeralTaskType, content: str) -> str:
    p = Prompts()
    prefixes = {
        EthemeralTaskType.FILE: p.fix_file,
        EthemeralTaskType.SECTION: p.fix_section,
        EthemeralTaskType.SECTION_EXTEND: p.extend_section,
        EthemeralTaskType.IMPROVE_EMAIL: p.fix_email,
        EthemeralTaskType.WRITE_EMAIL: p.write_email,
    }
    prefix = prefixes.get(task_type, "")
    return f"{prefix}\n\n{content}" if prefix else content


def get_system_message(task_type: EthemeralTaskType | ConversationTaskType) -> str:
    base = "You are a highly efficient AI assistant. "

    directives = {
        EthemeralTaskType.FILE: (
            "Act as a Senior Developer. Your goal is technical perfection. "
            "Correct syntax, improve logic, and return only the code/content "
            "without conversational filler."
        ),
        EthemeralTaskType.SECTION: (
            "Act as a meticulous Copy Editor. Change only what is necessary "
            "to fix errors or improve clarity. Do not rewrite the entire context."
        ),
        EthemeralTaskType.SECTION_EXTEND: (
            "Act as a Creative Partner. Expand the provided text while "
            "strictly mimicking the user's existing tone, vocabulary, and rhythm."
        ),
        EthemeralTaskType.IMPROVE_EMAIL: (
            "Act as a Corporate Communications Expert. Focus on making the "
            "email more professional, persuasive, and concise."
        ),
        EthemeralTaskType.WRITE_EMAIL: (
            "Act as a Ghostwriter. Draft a clear, polite, and effective email "
            "based on the provided points. Ensure a strong subject line."
        ),
    }

    return base + directives.get(task_type, "Provide accurate and helpful assistance.")
