import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from . import db as database
from .models import (
    EmailRequest,
    EthemeralTaskType,
    FileRequest,
    SectionRequest,
    SectionResponse,
    get_system_message,
    get_user_message,
)
from .ollamatools import chat_ollama

logger = logging.getLogger(__name__)

database.Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Server starting up")
    yield
    logger.info("Server shutting down — closing database connections")
    database.engine.dispose()


# Dependency to get the DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def root():
    return Response(status_code=status.HTTP_200_OK)


def _run_task(task_type: EthemeralTaskType, content: str, model) -> SectionResponse:
    system_prompt = get_system_message(task_type)
    user_input = get_user_message(task_type, content)
    ollama_message = (
        chat_ollama(user_input, system_prompt)
        if model is None
        else chat_ollama(user_input, system_prompt, model)
    )
    result = ollama_message.content
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama message has no content!\nResponse:\n{ollama_message}\n",
        )
    return SectionResponse(content=result, length=len(result))


@app.post("/section/improve")
async def fix_section(
    section_request: SectionRequest, db: Session = Depends(get_db)
) -> SectionResponse:
    # @todo add the db job persistence
    return _run_task(
        EthemeralTaskType.SECTION, section_request.content, section_request.model
    )


@app.post("/section/extend")
async def extend_section(
    section_request: SectionRequest, db: Session = Depends(get_db)
) -> SectionResponse:
    # @todo add the db job persistence
    return _run_task(
        EthemeralTaskType.SECTION_EXTEND, section_request.content, section_request.model
    )


@app.post("/file/improve")
async def fix_file(
    file_request: FileRequest, db: Session = Depends(get_db)
) -> SectionResponse:
    # @todo add the db job persistence
    return _run_task(EthemeralTaskType.FILE, file_request.content, file_request.model)


@app.post("/email/improve")
async def improve_email(
    email_request: EmailRequest, db: Session = Depends(get_db)
) -> SectionResponse:
    # @todo add the db job persistence
    return _run_task(
        EthemeralTaskType.IMPROVE_EMAIL, email_request.content, email_request.model
    )


@app.post("/email/write")
async def write_email(
    email_request: EmailRequest, db: Session = Depends(get_db)
) -> SectionResponse:
    # @todo add the db job persistence
    return _run_task(
        EthemeralTaskType.WRITE_EMAIL, email_request.content, email_request.model
    )
