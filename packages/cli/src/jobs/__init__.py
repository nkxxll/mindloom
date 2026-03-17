# @app.get("/jobs", response_model=list[JobResponse])
# async def list_jobs(db: CassandraSession = Depends(get_db)):
#     return database.get_all_jobs(db)


# @app.get("/jobs/{job_id}", response_model=JobResponse)
# async def get_job(job_id: int, db: CassandraSession = Depends(get_db)):
#     job = database.get_job_by_id(db, job_id)
#     if job is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
#     return job


# @app.post("/jobs/{job_id}/restart", response_model=JobResponse)
# async def restart_job(job_id: int, db: CassandraSession = Depends(get_db)):
#     job = database.get_job_by_id(db, job_id)
#     if job is None:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
#     task_type = EthemeralTaskType(int(job.task_type))
#     database.update_job_status(db, job_id, Status.RUNNING)
#     try:
#         result = _run_task(task_type, job.content, None)
#         return database.update_job_status(db, job_id, Status.COMPLETED, result=result.content)
#     except Exception:
#         database.update_job_status(db, job_id, Status.FAILED)
#         raise
import httpx
from mindloom_core.models import JobResponse


class JobsRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class GetJobsError(JobsRequestError):
    def __init__(
        self, status_code: int, message="Failed to get jobs: non 200 status code."
    ):
        super().__init__(status_code=status_code, message=message)


class GetJobByIdError(JobsRequestError):
    def __init__(
        self,
        status_code: int,
        message="Failed to get job: non 200 status code.",
    ):
        super().__init__(status_code=status_code, message=message)


class RestartJobError(JobsRequestError):
    def __init__(
        self,
        status_code: int,
        message="Failed to restart job: non 200 status code.",
    ):
        super().__init__(status_code=status_code, message=message)


class Jobs:
    def __init__(self, config):
        self.config = config

    def _parse_job_response(
        self,
        response: httpx.Response,
        *,
        error_type: type[JobsRequestError],
        error_message: str,
    ) -> JobResponse:
        if response.status_code == 200:
            return JobResponse.model_validate(response.json())
        raise error_type(status_code=response.status_code, message=error_message)

    def get_jobs(self) -> list[JobResponse]:
        response = httpx.get(f"{self.config.host}/jobs")
        if response.status_code == 200:
            jobs = [JobResponse.model_validate(u) for u in response.json()]
            return jobs
        raise GetJobsError(status_code=response.status_code)

    def get_job_by_id(self, job_id: int) -> JobResponse:
        response = httpx.get(f"{self.config.host}/jobs/{job_id}")
        return self._parse_job_response(
            response,
            error_type=GetJobByIdError,
            error_message=f"Failed to get job {job_id}: non 200 status code.",
        )

    def restart_by_id(self, job_id: int) -> JobResponse:
        response = httpx.post(f"{self.config.host}/jobs/{job_id}/restart")
        return self._parse_job_response(
            response,
            error_type=RestartJobError,
            error_message=f"Failed to restart job {job_id}: non 200 status code.",
        )
