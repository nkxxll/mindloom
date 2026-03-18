import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.cluster import Session as CassandraSession
from cassandra.policies import AddressTranslator, WhiteListRoundRobinPolicy
from cassandra.query import dict_factory
from dotenv import load_dotenv

from mindloom_core.models import Job, JobCreate, Status

logger = logging.getLogger(__name__)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _LocalAddressTranslator(AddressTranslator):
    """Maps any discovered Cassandra host address back to the first contact point.

    This is needed when Cassandra runs in Docker and advertises its container-internal
    IP (e.g. 172.19.0.2) which is unreachable from the host.
    """

    def __init__(self, target: str) -> None:
        self._target = target

    def translate(self, addr: str) -> str:
        return self._target


load_dotenv()


@dataclass(frozen=True)
class CassandraSettings:
    contact_points: list[str]
    port: int
    username: str | None
    password: str | None
    keyspace: str
    table: str
    replication_factor: int


@dataclass(frozen=True)
class WorkerSettings:
    poll_interval_seconds: int
    enabled: bool


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _read_settings() -> CassandraSettings:
    contact_points = [
        part.strip()
        for part in os.getenv("CASSANDRA_CONTACT_POINTS", "127.0.0.1").split(",")
        if part.strip()
    ]
    if not contact_points:
        msg = "CASSANDRA_CONTACT_POINTS must include at least one host"
        raise ValueError(msg)

    keyspace = os.getenv("CASSANDRA_KEYSPACE", "mindloom")
    table = os.getenv("CASSANDRA_TABLE", "jobs")
    for identifier_name, identifier_value in (
        ("CASSANDRA_KEYSPACE", keyspace),
        ("CASSANDRA_TABLE", table),
    ):
        if not _IDENTIFIER_PATTERN.match(identifier_value):
            msg = (
                f"{identifier_name} must match pattern "
                f"{_IDENTIFIER_PATTERN.pattern}; got {identifier_value!r}"
            )
            raise ValueError(msg)

    username = _optional_env("CASSANDRA_USERNAME")
    password = _optional_env("CASSANDRA_PASSWORD")
    if bool(username) != bool(password):
        msg = "CASSANDRA_USERNAME and CASSANDRA_PASSWORD must either both be set or both be unset"
        raise ValueError(msg)

    return CassandraSettings(
        contact_points=contact_points,
        port=int(os.getenv("CASSANDRA_PORT", "9042")),
        username=username,
        password=password,
        keyspace=keyspace,
        table=table,
        replication_factor=int(os.getenv("CASSANDRA_REPLICATION_FACTOR", "1")),
    )


def _read_worker_settings() -> WorkerSettings:
    return WorkerSettings(
        poll_interval_seconds=int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "600")),
        enabled=os.getenv("WORKER_ENABLED", "true").lower() in ("true", "1", "yes"),
    )


SETTINGS = _read_settings()
WORKER_SETTINGS = _read_worker_settings()

cluster: Cluster | None = None
session: CassandraSession | None = None


def init_db() -> CassandraSession:
    global cluster, session

    if session is not None:
        return session

    auth_provider = None
    if SETTINGS.username and SETTINGS.password:
        auth_provider = PlainTextAuthProvider(
            username=SETTINGS.username,
            password=SETTINGS.password,
        )

    cluster = Cluster(
        contact_points=SETTINGS.contact_points,
        port=SETTINGS.port,
        auth_provider=auth_provider,
        load_balancing_policy=WhiteListRoundRobinPolicy(SETTINGS.contact_points),
        address_translator=_LocalAddressTranslator(SETTINGS.contact_points[0]),
    )
    session = cluster.connect()
    session.row_factory = dict_factory

    session.execute(
        f"CREATE KEYSPACE IF NOT EXISTS {SETTINGS.keyspace} "
        "WITH replication = "
        f"{{'class': 'SimpleStrategy', 'replication_factor': {SETTINGS.replication_factor}}}"
    )
    session.set_keyspace(SETTINGS.keyspace)
    session.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SETTINGS.table} (
            id bigint PRIMARY KEY,
            task_type text,
            content text,
            result text,
            status text,
            created_at timestamp,
            updated_at timestamp,
            dependencies text
        )
        """
    )

    # Migration: Add dependencies column if it doesn't exist
    try:
        session.execute(
            f"ALTER TABLE {SETTINGS.table} ADD dependencies text"
        )
        logger.info("Added 'dependencies' column to %s table", SETTINGS.table)
    except Exception:
        # Column already exists, ignore the error
        pass

    logger.info(
        "Connected to Cassandra at %s:%s (%s.%s)",
        ",".join(SETTINGS.contact_points),
        SETTINGS.port,
        SETTINGS.keyspace,
        SETTINGS.table,
    )
    return session


def close_db() -> None:
    global cluster, session

    if session is not None:
        session.shutdown()
        session = None
    if cluster is not None:
        cluster.shutdown()
        cluster = None


def get_session() -> CassandraSession:
    return init_db()


def _row_to_job(row: dict[str, Any]) -> Job:
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


def _new_job_id() -> int:
    return time.time_ns()


def create_job(db: CassandraSession, job_data: JobCreate) -> Job:
    """Create a new job in the database.

    If the job content contains template placeholders ({{job_id}}), they are
    extracted and stored as dependencies. The job status is set to WAITING_FOR
    if dependencies exist, otherwise PENDING.

    Args:
        db: Database session
        job_data: Job creation data

    Returns:
        Created Job object

    Raises:
        ValueError: If template validation fails or circular dependencies detected
    """
    import json
    from .template_parser import extract_job_ids, validate_template

    created_at = datetime.now(timezone.utc)

    # Extract dependencies from content
    dependency_ids = []
    dependencies_json = None
    initial_status = Status.PENDING.value

    if job_data.content:
        # Validate template syntax
        error = validate_template(job_data.content)
        if error:
            raise ValueError(f"Invalid template: {error}")

        # Extract job IDs
        dependency_ids = extract_job_ids(job_data.content)

        if dependency_ids:
            # Validate that referenced jobs exist
            for dep_id in dependency_ids:
                dep_job = get_job_by_id(db, dep_id)
                if dep_job is None:
                    raise ValueError(f"Dependency job {dep_id} does not exist")

            # Store dependencies as JSON
            dependencies_json = json.dumps(dependency_ids)
            initial_status = Status.WAITING_FOR.value

            logger.info(
                "Creating job with %d dependencies: %s",
                len(dependency_ids),
                dependency_ids
            )

    # Allow explicit dependencies from job_data (for direct API use)
    if job_data.dependencies:
        dependencies_json = job_data.dependencies
        initial_status = Status.WAITING_FOR.value

    job = Job(
        id=_new_job_id(),
        task_type=str(job_data.task_type.value),
        content=job_data.content,
        result=None,
        status=initial_status,
        created_at=created_at,
        updated_at=created_at,
        dependencies=dependencies_json,
    )

    db.execute(
        f"""
        INSERT INTO {SETTINGS.table}
        (id, task_type, content, result, status, created_at, updated_at, dependencies)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            job.id,
            job.task_type,
            job.content,
            job.result,
            job.status,
            job.created_at,
            job.updated_at,
            job.dependencies,
        ),
    )
    return job


def update_job_status(
    db: CassandraSession, job_id: int, status: Status, result: str | None = None
) -> Job | None:
    existing_job = get_job_by_id(db, job_id)
    if existing_job is None:
        return None

    updated_result = existing_job.result if result is None else result
    updated_at = datetime.now(timezone.utc)
    db.execute(
        f"""
        UPDATE {SETTINGS.table}
        SET status = %s, result = %s, updated_at = %s
        WHERE id = %s
        """,
        (status.value, updated_result, updated_at, job_id),
    )
    return existing_job.model_copy(
        update={
            "status": status.value,
            "result": updated_result,
            "updated_at": updated_at,
        }
    )


def get_all_jobs(db: CassandraSession) -> list[Job]:
    rows = db.execute(
        f"""
        SELECT id, task_type, content, result, status, created_at, updated_at, dependencies
        FROM {SETTINGS.table}
        """
    )
    jobs = [_row_to_job(row) for row in rows]
    return sorted(jobs, key=lambda job: job.created_at, reverse=True)


def get_job_by_id(db: CassandraSession, job_id: int) -> Job | None:
    row = db.execute(
        f"""
        SELECT id, task_type, content, result, status, created_at, updated_at, dependencies
        FROM {SETTINGS.table}
        WHERE id = %s
        """,
        (job_id,),
    ).one()
    if row is None:
        return None
    return _row_to_job(row)
