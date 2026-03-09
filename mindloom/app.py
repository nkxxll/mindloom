from . import db as database
from fastapi import Depends, FastAPI, Response, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from .models import (
    EthemeralTaskType,
    SectionRequest,
    SectionResponse,
    get_system_message,
)
from .ollamatools import chat_ollama

database.Base.metadata.create_all(bind=database.engine)

# Dependency to get the DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()


@app.get("/health")
async def root():
    return Response(status_code=status.HTTP_200_OK)


@app.post("/section")
async def fix_section(
    section_request: SectionRequest, db: Session = Depends(get_db)
) -> SectionResponse:
    # @todo add the db job persistence
    task_type = EthemeralTaskType.SECTION  # fix section
    user_input = section_request.content
    system_prompt = get_system_message(task_type)
    model = section_request.model
    ollama_message = (
        chat_ollama(user_input, system_prompt)
        if model is None
        else chat_ollama(user_input, system_prompt, model)
    )
    content = ollama_message.content
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama message has no content!\nResponse:\n{ollama_message}\n",
        )
    response = SectionResponse(content=content, length=len(content))
    return response
