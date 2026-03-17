# Plan: Auto-Generate Readable Job Titles

## Problem

Jobs currently have no human-readable title — the job list shows raw `task_type`, `id`, and truncated `content`. When browsing `/jobs`, everything looks the same.

## Idea

After a job is created, fire off a cheap, fast LLM call (`qwen3.5:0.6b` or similar) to generate a short, descriptive title from the job's `content`. This runs asynchronously so it doesn't slow down the main task.

---

## 1. Schema change — add `title` column

**File:** `packages/server/src/mindloom/db.py`

Add a `title text` column to the jobs table:

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id bigint PRIMARY KEY,
    task_type text,
    title text,          -- NEW
    content text,
    result text,
    status text,
    created_at timestamp,
    updated_at timestamp
)
```

For the existing table, run an `ALTER TABLE` migration on startup if the column doesn't exist:

```python
session.execute(
    f"ALTER TABLE {SETTINGS.table} ADD title text"
)
```

Wrap in a try/except to silently ignore if the column already exists (Cassandra raises `InvalidRequest`).

---

## 2. Update models

**File:** `packages/server/src/mindloom/models.py`

### 2a. Add `title` to `Job` and `JobResponse`

```python
class Job(BaseModel):
    id: int
    task_type: str
    title: Optional[str]       # NEW
    content: Optional[str]
    result: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

class JobResponse(BaseModel):
    id: int
    task_type: str
    title: Optional[str]       # NEW
    content: Optional[str]
    result: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
```

### 2b. Add the title model constant

```python
class Model(StrEnum):
    # ...existing...
    TITLE_GEN = "qwen3:0.6b"  # tiny model, fast, only used for titles

    @property
    def supports_thinking(self) -> bool:
        return self in {Model.QWEN, Model.QWEN314}
```

---

## 3. Add DB helpers

**File:** `packages/server/src/mindloom/db.py`

### 3a. Update `_row_to_job` to read `title`

```python
def _row_to_job(row: dict[str, Any]) -> Job:
    return Job(
        id=int(row["id"]),
        task_type=str(row["task_type"]),
        title=row.get("title"),
        ...
    )
```

### 3b. Update `create_job` to include `title` (initially `None`)

Add `title` to the INSERT statement.

### 3c. Add `update_job_title`

```python
def update_job_title(db: CassandraSession, job_id: int, title: str) -> None:
    db.execute(
        f"UPDATE {SETTINGS.table} SET title = %s WHERE id = %s",
        (title, job_id),
    )
```

### 3d. Update all SELECT queries to include `title`

---

## 4. Title generation function

**File:** `packages/server/src/mindloom/ollamatools.py`

Add a dedicated function that calls the tiny model:

```python
TITLE_MODEL = "qwen3:0.6b"

def generate_title(content: str, task_type: str) -> str:
    """Generate a short readable title (5-10 words) for a job."""
    response = ollama.chat(
        model=TITLE_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Generate a short, descriptive title (5-10 words max) "
                    "for the following user request. Return ONLY the title, "
                    "no quotes, no explanation."
                ),
            },
            {
                "role": "user",
                "content": f"Task type: {task_type}\n\nContent:\n{content[:500]}",
            },
        ],
    )
    return response.message.content.strip()
```

Key design choices:
- **Truncate content to 500 chars** — the tiny model doesn't need the full text, and this keeps it fast.
- **No thinking mode** — the 0.6b model doesn't support it and doesn't need it for this task.
- **Include `task_type`** — gives the model context about what kind of title to generate (e.g. "email" vs "code fix").

---

## 5. Async title generation in endpoints

**File:** `packages/server/src/mindloom/app.py`

Use `asyncio.to_thread` + `asyncio.create_task` to fire the title generation in the background so it doesn't block the main LLM task:

```python
import asyncio
from .ollamatools import generate_title

async def _generate_title_bg(db, job_id: int, content: str, task_type: str):
    """Fire-and-forget background title generation."""
    try:
        title = await asyncio.to_thread(generate_title, content, task_type)
        await asyncio.to_thread(database.update_job_title, db, job_id, title)
    except Exception:
        logger.warning("Failed to generate title for job %s", job_id, exc_info=True)
```

Then in each endpoint, after `create_job`:

```python
@app.post("/section/improve")
async def fix_section(req: SectionRequest, db=Depends(get_db)) -> SectionResponse:
    job = database.create_job(db, JobCreate(...))
    asyncio.create_task(_generate_title_bg(db, job.id, req.content, "SECTION"))
    try:
        result = _run_task(...)
        ...
```

The title task runs concurrently with the main (heavier) LLM call. The tiny model will finish long before the main model does.

---

## 6. Fallback title

If title generation fails or hasn't completed yet, the API returns `title: null`. The frontend/client should fall back to a generated label like:

```
"{task_type} — {created_at formatted}"
```

This keeps the system resilient — titles are nice-to-have, never blocking.

---

## 7. Endpoint to manually set/regenerate title

**File:** `packages/server/src/mindloom/app.py`

Optional but useful:

```python
@app.patch("/jobs/{job_id}/title")
async def set_job_title(job_id: int, title: str, db=Depends(get_db)):
    """Manually override a job's title."""
    database.update_job_title(db, job_id, title)
    return {"id": job_id, "title": title}

@app.post("/jobs/{job_id}/regenerate-title")
async def regenerate_title(job_id: int, db=Depends(get_db)):
    """Re-run title generation for an existing job."""
    job = database.get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404)
    title = generate_title(job.content or "", job.task_type)
    database.update_job_title(db, job_id, title)
    return {"id": job_id, "title": title}
```

---

## 8. Tests

- **Unit test `generate_title`** — mock `ollama.chat`, assert output is stripped and reasonable length.
- **Integration test** — create a job, verify title is `None` initially, then after background task completes it's populated.
- **Fallback test** — mock `ollama.chat` to raise, verify job still completes successfully with `title=None`.

---

## Implementation order

1. DB migration + model changes (`db.py`, `models.py`)
2. `generate_title` function (`ollamatools.py`)
3. Background task wiring in endpoints (`app.py`)
4. Optional PATCH/regenerate endpoints (`app.py`)
5. Tests
