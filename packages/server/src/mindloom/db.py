from sqlalchemy import Column, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Job, JobCreate, Status

# The 'check_same_thread' argument is specific to SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_job(db: Session, job_data: JobCreate):
    db_job = Job(
        task_type=job_data.task_type.value, content=job_data.content, status="pending"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def update_job_status(db: Session, job_id: int, status: Status):
    db_job = db.query(Job).filter(Job.id == job_id).first()
    if db_job:
        db_job.status = Column(status.value)
        db.commit()
        db.refresh(db_job)
    return db_job


def get_all_jobs(db: Session):
    return db.query(Job).all()


def get_job_by_id(db: Session, job_id: int):
    return db.query(Job).filter(Job.id == job_id).first()
