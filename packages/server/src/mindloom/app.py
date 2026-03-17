import logging
from contextlib import asynccontextmanager

from cassandra.cluster import Session as CassandraSession
from fastapi import Depends, FastAPI, Response, status
from fastapi.exceptions import HTTPException

from . import db as database
from .models import (
    CommitMessageRequest,
    EmailRequest,
    EthemeralTaskType,
    ExplainCodeRequest,
    ExtractActionsRequest,
    FileRequest,
    GenerateTestsRequest,
    JobCreate,
    JobResponse,
    ProofreadRequest,
    RewriteToneRequest,
    SectionRequest,
    SectionResponse,
    Status,
    SummarizeRequest,
    TranslateRequest,
    get_system_message,
    get_user_message,
)
from .ollamatools import chat_ollama

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Server starting up")
    database.init_db()
    yield
    logger.info("Server shutting down — closing database connections")
    database.close_db()


# Dependency to get the DB session
def get_db():
    yield database.get_session()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def root():
    return Response(status_code=status.HTTP_200_OK)


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(db: CassandraSession = Depends(get_db)):
    return database.get_all_jobs(db)


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: CassandraSession = Depends(get_db)):
    job = database.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
    return job


@app.post("/jobs/{job_id}/restart", response_model=JobResponse)
async def restart_job(job_id: int, db: CassandraSession = Depends(get_db)):
    job = database.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
    task_type = EthemeralTaskType(int(job.task_type))
    database.update_job_status(db, job_id, Status.RUNNING)
    try:
        result = _run_task(task_type, job.content, None)
        return database.update_job_status(db, job_id, Status.COMPLETED, result=result.content)
    except Exception:
        database.update_job_status(db, job_id, Status.FAILED)
        raise


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
    section_request: SectionRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.SECTION, content=section_request.content))
    try:
        result = _run_task(EthemeralTaskType.SECTION, section_request.content, section_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/section/extend")
async def extend_section(
    section_request: SectionRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.SECTION_EXTEND, content=section_request.content))
    try:
        result = _run_task(EthemeralTaskType.SECTION_EXTEND, section_request.content, section_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/file/improve")
async def fix_file(
    file_request: FileRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.FILE, content=file_request.content))
    try:
        result = _run_task(EthemeralTaskType.FILE, file_request.content, file_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/email/improve")
async def improve_email(
    email_request: EmailRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.IMPROVE_EMAIL, content=email_request.content))
    try:
        result = _run_task(EthemeralTaskType.IMPROVE_EMAIL, email_request.content, email_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/email/write")
async def write_email(
    email_request: EmailRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.WRITE_EMAIL, content=email_request.content))
    try:
        result = _run_task(EthemeralTaskType.WRITE_EMAIL, email_request.content, email_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/summarize")
async def summarize(
    summarize_request: SummarizeRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    content = summarize_request.content
    if summarize_request.max_length is not None:
        content = f"Maximum length: {summarize_request.max_length}\n\n{content}"
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.SUMMARIZE, content=content))
    try:
        result = _run_task(EthemeralTaskType.SUMMARIZE, content, summarize_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/translate")
async def translate(
    translate_request: TranslateRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    metadata = [f"Target language: {translate_request.target_language}"]
    if translate_request.source_language:
        metadata.append(f"Source language: {translate_request.source_language}")
    metadata_block = "\n".join(metadata)
    content = f"{metadata_block}\n\n{translate_request.content}"
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.TRANSLATE, content=content))
    try:
        result = _run_task(EthemeralTaskType.TRANSLATE, content, translate_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/code/explain")
async def explain_code(
    explain_code_request: ExplainCodeRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    content = explain_code_request.content
    if explain_code_request.language:
        content = f"Language: {explain_code_request.language}\n\n{content}"
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.EXPLAIN_CODE, content=content))
    try:
        result = _run_task(EthemeralTaskType.EXPLAIN_CODE, content, explain_code_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/git/commit-message")
async def generate_commit_message(
    commit_message_request: CommitMessageRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(
        db,
        JobCreate(task_type=EthemeralTaskType.COMMIT_MESSAGE, content=commit_message_request.content),
    )
    try:
        result = _run_task(
            EthemeralTaskType.COMMIT_MESSAGE,
            commit_message_request.content,
            commit_message_request.model,
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/extract/actions")
async def extract_actions(
    extract_actions_request: ExtractActionsRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(
        db,
        JobCreate(task_type=EthemeralTaskType.EXTRACT_ACTIONS, content=extract_actions_request.content),
    )
    try:
        result = _run_task(
            EthemeralTaskType.EXTRACT_ACTIONS,
            extract_actions_request.content,
            extract_actions_request.model,
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/rewrite/tone")
async def rewrite_tone(
    rewrite_tone_request: RewriteToneRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    content = f"Target tone: {rewrite_tone_request.target_tone}\n\n{rewrite_tone_request.content}"
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.REWRITE_TONE, content=content))
    try:
        result = _run_task(EthemeralTaskType.REWRITE_TONE, content, rewrite_tone_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/proofread")
async def proofread(
    proofread_request: ProofreadRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    job = database.create_job(
        db,
        JobCreate(task_type=EthemeralTaskType.PROOFREAD, content=proofread_request.content),
    )
    try:
        result = _run_task(EthemeralTaskType.PROOFREAD, proofread_request.content, proofread_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/code/generate-tests")
async def generate_tests(
    generate_tests_request: GenerateTestsRequest, db: CassandraSession = Depends(get_db)
) -> SectionResponse:
    metadata: list[str] = []
    if generate_tests_request.language:
        metadata.append(f"Language: {generate_tests_request.language}")
    if generate_tests_request.framework:
        metadata.append(f"Framework: {generate_tests_request.framework}")
    metadata_block = "\n".join(metadata)
    content = (
        f"{metadata_block}\n\n{generate_tests_request.content}"
        if metadata
        else generate_tests_request.content
    )
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.GENERATE_TESTS, content=content))
    try:
        result = _run_task(EthemeralTaskType.GENERATE_TESTS, content, generate_tests_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise
