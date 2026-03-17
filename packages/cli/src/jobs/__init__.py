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


class GetJobsError(Exception):
    def __init__(
        self, status_code: int, message="Failed to get jobs: non 200 status code."
    ):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class Jobs:
    def __init__(self, config):
        self.config = config

    def get_jobs(self):
        response = httpx.get(f"{self.config.host}/jobs")
        if response.status_code == 200:
            jobs = [JobResponse.model_validate(u) for u in response.json()]
            return jobs
        else:
            raise GetJobsError(status_code=response.status_code)
