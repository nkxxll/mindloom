"""Background worker for processing jobs with dependencies.

This module implements a lightweight background worker using threading.Timer
that polls for jobs in WAITING_FOR status and executes them when their
dependencies are satisfied.
"""

import json
import logging
import threading
from typing import Callable, Optional

from cassandra.cluster import Session as CassandraSession

from .db import SETTINGS, WORKER_SETTINGS, get_session
from .models import Job, Status
from .template_parser import replace_templates

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker for processing dependent jobs.

    Polls the database at regular intervals for jobs with WAITING_FOR status,
    checks if their dependencies are satisfied, and executes them when ready.
    """

    def __init__(
        self,
        poll_interval: Optional[int] = None,
        job_executor: Optional[Callable[[CassandraSession, Job], None]] = None,
    ):
        """Initialize the background worker.

        Args:
            poll_interval: Seconds between polling cycles (default from config)
            job_executor: Optional callable to execute jobs (for testing)
        """
        self.poll_interval = poll_interval or WORKER_SETTINGS.poll_interval_seconds
        self.job_executor = job_executor
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._lock = threading.Lock()
        logger.info(
            "Initialized BackgroundWorker with poll_interval=%ds", self.poll_interval
        )

    def start(self) -> None:
        """Start the background worker polling cycle."""
        with self._lock:
            if self._running:
                logger.warning("Worker already running")
                return

            self._running = True
            logger.info("Starting background worker")
            self._schedule_next_poll()

    def stop(self) -> None:
        """Stop the background worker and cancel pending polls."""
        with self._lock:
            if not self._running:
                return

            logger.info("Stopping background worker")
            self._running = False

            if self._timer:
                self._timer.cancel()
                self._timer = None

    def _schedule_next_poll(self) -> None:
        """Schedule the next polling cycle."""
        if not self._running:
            return

        self._timer = threading.Timer(self.poll_interval, self._poll_cycle)
        self._timer.daemon = True
        self._timer.start()

    def _poll_cycle(self) -> None:
        """Execute one polling cycle: find and process waiting jobs."""
        try:
            logger.debug("Starting poll cycle")
            self.poll_jobs()
        except Exception as e:
            logger.error("Error in poll cycle: %s", e, exc_info=True)
        finally:
            # Schedule next poll regardless of errors
            self._schedule_next_poll()

    def poll_jobs(self) -> None:
        """Query for WAITING_FOR jobs and process them if dependencies are ready.

        This is the main worker logic executed on each poll cycle.
        """
        db = get_session()

        # Query for jobs waiting for dependencies
        rows = db.execute(
            f"""
            SELECT id, task_type, content, result, status, created_at, updated_at, dependencies
            FROM {SETTINGS.table}
            WHERE status = %s
            ALLOW FILTERING
            """,
            (Status.WAITING_FOR.value,),
        )

        waiting_jobs = [self._row_to_job(row) for row in rows]

        if not waiting_jobs:
            logger.debug("No jobs waiting for dependencies")
            return

        logger.info("Found %d jobs waiting for dependencies", len(waiting_jobs))

        # Process each waiting job
        for job in waiting_jobs:
            try:
                self._process_waiting_job(db, job)
            except Exception as e:
                logger.error(
                    "Error processing job %d: %s", job.id, e, exc_info=True
                )

    def _row_to_job(self, row: dict) -> Job:
        """Convert database row to Job object."""
        return Job(
            id=int(row["id"]),
            task_type=str(row["task_type"]),
            content=row["content"],
            result=row["result"],
            status=str(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            dependencies=row.get("dependencies"),
        )

    def _process_waiting_job(self, db: CassandraSession, job: Job) -> None:
        """Process a single waiting job.

        Checks dependencies, replaces templates if ready, and executes the job.

        Args:
            db: Database session
            job: Job to process
        """
        logger.debug("Processing job %d", job.id)

        # Parse dependencies
        if not job.dependencies:
            logger.warning("Job %d has WAITING_FOR status but no dependencies", job.id)
            self._fail_job(db, job.id, "No dependencies specified")
            return

        try:
            dependency_ids = json.loads(job.dependencies)
        except json.JSONDecodeError as e:
            logger.error("Job %d has invalid dependencies JSON: %s", job.id, e)
            self._fail_job(db, job.id, f"Invalid dependencies format: {e}")
            return

        if not dependency_ids:
            logger.warning("Job %d has empty dependencies list", job.id)
            self._fail_job(db, job.id, "Empty dependencies list")
            return

        # Check if dependencies are ready
        ready, job_results = self._check_dependencies_ready(db, dependency_ids, job.id)

        if not ready:
            # Dependencies not yet ready, keep waiting
            return

        # Replace templates in content
        if job.content:
            resolved_content = replace_templates(job.content, job_results)
            logger.info(
                "Job %d: Resolved content with %d dependencies",
                job.id,
                len(job_results),
            )
        else:
            resolved_content = job.content

        # Execute the job
        self._execute_job(db, job, resolved_content)

    def _check_dependencies_ready(
        self, db: CassandraSession, dependency_ids: list[int], job_id: int
    ) -> tuple[bool, dict[int, str]]:
        """Check if all dependencies are completed and collect their results.

        Args:
            db: Database session
            dependency_ids: List of job IDs to check
            job_id: ID of the waiting job (for logging)

        Returns:
            Tuple of (ready, results) where ready is True if all deps completed,
            and results is dict mapping job_id to result content
        """
        job_results = {}

        for dep_id in dependency_ids:
            row = db.execute(
                f"""
                SELECT id, status, result
                FROM {SETTINGS.table}
                WHERE id = %s
                """,
                (dep_id,),
            ).one()

            if row is None:
                logger.error("Job %d depends on non-existent job %d", job_id, dep_id)
                self._fail_job(db, job_id, f"Dependency job {dep_id} not found")
                return False, {}

            status = str(row["status"])

            if status == Status.FAILED.value:
                logger.info(
                    "Job %d dependency %d has failed, failing dependent job",
                    job_id,
                    dep_id,
                )
                self._fail_job(db, job_id, f"Dependency job {dep_id} failed")
                return False, {}

            if status != Status.COMPLETED.value:
                logger.debug(
                    "Job %d waiting: dependency %d has status %s",
                    job_id,
                    dep_id,
                    status,
                )
                return False, {}

            # Dependency is completed, collect result
            result = row["result"] or ""
            job_results[dep_id] = result

        # All dependencies completed!
        logger.info(
            "Job %d: All %d dependencies completed", job_id, len(dependency_ids)
        )
        return True, job_results

    def _execute_job(
        self, db: CassandraSession, job: Job, resolved_content: Optional[str]
    ) -> None:
        """Execute a job with resolved content.

        Args:
            db: Database session
            job: Original job
            resolved_content: Content with templates replaced
        """
        # Update job with resolved content and mark as running
        from datetime import datetime, timezone

        db.execute(
            f"""
            UPDATE {SETTINGS.table}
            SET status = %s, content = %s, updated_at = %s
            WHERE id = %s
            """,
            (
                Status.RUNNING.value,
                resolved_content,
                datetime.now(timezone.utc),
                job.id,
            ),
        )

        logger.info("Job %d: Marked as RUNNING, executing", job.id)

        # Execute the job using provided executor or default
        if self.job_executor:
            try:
                updated_job = Job(
                    id=job.id,
                    task_type=job.task_type,
                    content=resolved_content,
                    result=job.result,
                    status=Status.RUNNING.value,
                    created_at=job.created_at,
                    updated_at=datetime.now(timezone.utc),
                    dependencies=job.dependencies,
                )
                self.job_executor(db, updated_job)
            except Exception as e:
                logger.error(
                    "Job executor failed for job %d: %s", job.id, e, exc_info=True
                )
                self._fail_job(db, job.id, str(e))
        else:
            logger.warning(
                "Job %d: No job executor configured, marking as completed (no-op)",
                job.id,
            )
            # Mark as completed with empty result for testing without executor
            db.execute(
                f"""
                UPDATE {SETTINGS.table}
                SET status = %s, updated_at = %s
                WHERE id = %s
                """,
                (
                    Status.COMPLETED.value,
                    datetime.now(timezone.utc),
                    job.id,
                ),
            )

    def _fail_job(self, db: CassandraSession, job_id: int, reason: str) -> None:
        """Mark a job as failed.

        Args:
            db: Database session
            job_id: Job to fail
            reason: Failure reason (logged)
        """
        from datetime import datetime, timezone

        logger.error("Failing job %d: %s", job_id, reason)

        db.execute(
            f"""
            UPDATE {SETTINGS.table}
            SET status = %s, result = %s, updated_at = %s
            WHERE id = %s
            """,
            (
                Status.FAILED.value,
                f"Failed: {reason}",
                datetime.now(timezone.utc),
                job_id,
            ),
        )
