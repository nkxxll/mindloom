import logging
from contextlib import asynccontextmanager

from cassandra.cluster import Session as CassandraSession
from fastapi import BackgroundTasks, Depends, FastAPI, Response, status
from fastapi.exceptions import HTTPException
from mindloom_core.models import (
    AskRequest,
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
    TaskResponse,
    TranslateRequest,
)

from . import db as database
from .db import WORKER_SETTINGS
from .models import (
    get_system_message,
    get_user_message,
)
from .ollamatools import chat_ollama

logger = logging.getLogger(__name__)
ASK_MARKDOWN_STYLE_HINT = (
    "Output format: markdown article\n"
    "Write a clear note-style answer with a title, short intro, section headings, "
    "and a brief summary."
)

# Global worker instance
_worker = None


def _execute_job_for_worker(db: CassandraSession, job) -> None:
    """Execute a job for the background worker.

    This function is called by the worker to execute jobs with resolved dependencies.
    """
    try:
        # Parse task type
        task_type = EthemeralTaskType(int(job.task_type))

        # Run the task
        result = _run_task(task_type, job.content or "", None)

        # Update job to completed
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        logger.info("Worker: Job %d completed successfully", job.id)
    except Exception as e:
        # Update job to failed
        database.update_job_status(db, job.id, Status.FAILED)
        logger.error("Worker: Job %d failed: %s", job.id, e, exc_info=True)
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker

    logger.info("Server starting up")
    database.init_db()

    # Start background worker if enabled
    if WORKER_SETTINGS.enabled:
        from .worker import BackgroundWorker

        logger.info("Starting background worker (enabled=%s)", WORKER_SETTINGS.enabled)
        _worker = BackgroundWorker(job_executor=_execute_job_for_worker)
        _worker.start()
    else:
        logger.info("Background worker disabled by configuration")

    yield

    # Stop worker on shutdown
    if _worker:
        logger.info("Stopping background worker")
        _worker.stop()

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )
    return job


@app.post("/jobs/{job_id}/restart", response_model=JobResponse)
async def restart_job(job_id: int, db: CassandraSession = Depends(get_db)):
    job = database.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )
    task_type = EthemeralTaskType(int(job.task_type))
    database.update_job_status(db, job_id, Status.RUNNING)
    try:
        if job.content is None:
            raise Exception("Content cannot be None, should never happen!")
        result = _run_task(task_type, job.content, None)
        return database.update_job_status(
            db, job_id, Status.COMPLETED, result=result.content
        )
    except Exception:
        database.update_job_status(db, job_id, Status.FAILED)
        raise


@app.get("/jobs/{job_id}/dependencies", response_model=list[JobResponse])
async def get_job_dependencies(job_id: int, db: CassandraSession = Depends(get_db)):
    """Get the list of jobs that the specified job depends on.

    Returns the full job objects for each dependency, including their current status.
    Useful for monitoring dependency chains and debugging.
    """
    import json

    job = database.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
        )

    if not job.dependencies:
        return []

    try:
        dependency_ids = json.loads(job.dependencies)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid dependencies format",
        )

    # Fetch each dependency job
    dependency_jobs = []
    for dep_id in dependency_ids:
        dep_job = database.get_job_by_id(db, dep_id)
        if dep_job:
            dependency_jobs.append(dep_job)

    return dependency_jobs


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


def _execute_async_job(
    db: CassandraSession, job_id: int, task_type: EthemeralTaskType, content: str, model
) -> None:
    """Execute a job asynchronously in the background."""
    try:
        database.update_job_status(db, job_id, Status.RUNNING)
        result = _run_task(task_type, content, model)
        database.update_job_status(db, job_id, Status.COMPLETED, result=result.content)
        logger.info("Async job %d completed successfully", job_id)
    except Exception as e:
        database.update_job_status(db, job_id, Status.FAILED)
        logger.error("Async job %d failed: %s", job_id, e, exc_info=True)


@app.post("/section/improve")
async def fix_section(
    section_request: SectionRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(task_type=EthemeralTaskType.SECTION, content=section_request.content),
    )

    if section_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.SECTION,
            section_request.content,
            section_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.SECTION, section_request.content, section_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/section/extend")
async def extend_section(
    section_request: SectionRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(
            task_type=EthemeralTaskType.SECTION_EXTEND, content=section_request.content
        ),
    )

    if section_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.SECTION_EXTEND,
            section_request.content,
            section_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.SECTION_EXTEND,
            section_request.content,
            section_request.model,
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/file/improve")
async def fix_file(
    file_request: FileRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.FILE, content=file_request.content)
    )

    if file_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.FILE,
            file_request.content,
            file_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.FILE, file_request.content, file_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/email/improve")
async def improve_email(
    email_request: EmailRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(
            task_type=EthemeralTaskType.IMPROVE_EMAIL, content=email_request.content
        ),
    )

    if email_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.IMPROVE_EMAIL,
            email_request.content,
            email_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.IMPROVE_EMAIL, email_request.content, email_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/email/write")
async def write_email(
    email_request: EmailRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(
            task_type=EthemeralTaskType.WRITE_EMAIL, content=email_request.content
        ),
    )

    if email_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.WRITE_EMAIL,
            email_request.content,
            email_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.WRITE_EMAIL, email_request.content, email_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/ask")
async def ask(
    ask_request: AskRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    content = ask_request.question
    if ask_request.markdown:
        content = f"{ASK_MARKDOWN_STYLE_HINT}\n\n{content}"

    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.ASK, content=content)
    )

    if ask_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.ASK,
            content,
            ask_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(EthemeralTaskType.ASK, content, ask_request.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/summarize")
async def summarize(
    summarize_request: SummarizeRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    content = summarize_request.content
    if summarize_request.max_length is not None:
        content = f"Maximum length: {summarize_request.max_length}\n\n{content}"
    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.SUMMARIZE, content=content)
    )

    if summarize_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.SUMMARIZE,
            content,
            summarize_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.SUMMARIZE, content, summarize_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/translate")
async def translate(
    translate_request: TranslateRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    metadata = [f"Target language: {translate_request.target_language}"]
    if translate_request.source_language:
        metadata.append(f"Source language: {translate_request.source_language}")
    metadata_block = "\n".join(metadata)
    content = f"{metadata_block}\n\n{translate_request.content}"
    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.TRANSLATE, content=content)
    )

    if translate_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.TRANSLATE,
            content,
            translate_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.TRANSLATE, content, translate_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/code/explain")
async def explain_code(
    explain_code_request: ExplainCodeRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    content = explain_code_request.content
    if explain_code_request.language:
        content = f"Language: {explain_code_request.language}\n\n{content}"
    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.EXPLAIN_CODE, content=content)
    )

    if explain_code_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.EXPLAIN_CODE,
            content,
            explain_code_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.EXPLAIN_CODE, content, explain_code_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/git/commit-message")
async def generate_commit_message(
    commit_message_request: CommitMessageRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(
            task_type=EthemeralTaskType.COMMIT_MESSAGE,
            content=commit_message_request.content,
        ),
    )

    if commit_message_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.COMMIT_MESSAGE,
            commit_message_request.content,
            commit_message_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.COMMIT_MESSAGE,
            commit_message_request.content,
            commit_message_request.model,
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/extract/actions")
async def extract_actions(
    extract_actions_request: ExtractActionsRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(
            task_type=EthemeralTaskType.EXTRACT_ACTIONS,
            content=extract_actions_request.content,
        ),
    )

    if extract_actions_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.EXTRACT_ACTIONS,
            extract_actions_request.content,
            extract_actions_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.EXTRACT_ACTIONS,
            extract_actions_request.content,
            extract_actions_request.model,
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/rewrite/tone")
async def rewrite_tone(
    rewrite_tone_request: RewriteToneRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    content = f"Target tone: {rewrite_tone_request.target_tone}\n\n{rewrite_tone_request.content}"
    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.REWRITE_TONE, content=content)
    )

    if rewrite_tone_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.REWRITE_TONE,
            content,
            rewrite_tone_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.REWRITE_TONE, content, rewrite_tone_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/proofread")
async def proofread(
    proofread_request: ProofreadRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
    job = database.create_job(
        db,
        JobCreate(
            task_type=EthemeralTaskType.PROOFREAD, content=proofread_request.content
        ),
    )

    if proofread_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.PROOFREAD,
            proofread_request.content,
            proofread_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.PROOFREAD,
            proofread_request.content,
            proofread_request.model,
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise


@app.post("/code/generate-tests")
async def generate_tests(
    generate_tests_request: GenerateTestsRequest,
    background_tasks: BackgroundTasks,
    db: CassandraSession = Depends(get_db),
) -> TaskResponse:
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
    job = database.create_job(
        db, JobCreate(task_type=EthemeralTaskType.GENERATE_TESTS, content=content)
    )

    if generate_tests_request.async_mode:
        background_tasks.add_task(
            _execute_async_job,
            db,
            job.id,
            EthemeralTaskType.GENERATE_TESTS,
            content,
            generate_tests_request.model,
        )
        return TaskResponse(
            job_id=job.id, status=Status.PENDING, created_at=job.created_at
        )

    try:
        result = _run_task(
            EthemeralTaskType.GENERATE_TESTS, content, generate_tests_request.model
        )
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return TaskResponse(
            job_id=job.id,
            status=Status.COMPLETED,
            content=result.content,
            length=result.length,
            created_at=job.created_at,
        )
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise
