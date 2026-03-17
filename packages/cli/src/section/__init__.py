# @app.post("/section/improve")
# async def fix_section(
#     section_request: SectionRequest, db: CassandraSession = Depends(get_db)
# ) -> SectionResponse:
#     job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.SECTION, content=section_request.content))
#     try:
#         result = _run_task(EthemeralTaskType.SECTION, section_request.content, section_request.model)
#         database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
#         return result
#     except Exception:
#         database.update_job_status(db, job.id, Status.FAILED)
#         raise


# @app.post("/section/extend")
# async def extend_section(
#     section_request: SectionRequest, db: CassandraSession = Depends(get_db)
# ) -> SectionResponse:
#     job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.SECTION_EXTEND, content=section_request.content))
#     try:
#         result = _run_task(EthemeralTaskType.SECTION_EXTEND, section_request.content, section_request.model)
#         database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
#         return result
#     except Exception:
#         database.update_job_status(db, job.id, Status.FAILED)
#         raise
