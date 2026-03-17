# Plan: New LLM Endpoints

## Overview

Add 8 new background LLM task types to Mindloom. Each follows the existing pattern: new `EthemeralTaskType` variant → prompt pair → thin endpoint in `app.py`.

---

## 1. Update `EthemeralTaskType` enum

**File:** `packages/server/src/mindloom/models.py`

Add new variants to the existing enum:

```python
class EthemeralTaskType(Enum):
    # existing
    FILE = auto()
    SECTION = auto()
    SECTION_EXTEND = auto()
    IMPROVE_EMAIL = auto()
    WRITE_EMAIL = auto()
    # new
    SUMMARIZE = auto()
    TRANSLATE = auto()
    EXPLAIN_CODE = auto()
    COMMIT_MESSAGE = auto()
    EXTRACT_ACTIONS = auto()
    REWRITE_TONE = auto()
    PROOFREAD = auto()
    GENERATE_TESTS = auto()
```

---

## 2. Add request models

**File:** `packages/server/src/mindloom/models.py`

Some endpoints need extra fields beyond `content`:

```python
class SummarizeRequest(BaseModel):
    content: str
    max_length: Optional[int] = None  # optional word/sentence cap
    model: Optional[Model] = None

class TranslateRequest(BaseModel):
    content: str
    target_language: str              # e.g. "German", "Spanish"
    source_language: Optional[str] = None
    model: Optional[Model] = None

class ExplainCodeRequest(BaseModel):
    content: str                      # the code snippet
    language: Optional[str] = None    # e.g. "Python", "Rust"
    model: Optional[Model] = None

class CommitMessageRequest(BaseModel):
    content: str                      # the diff
    model: Optional[Model] = None

class ExtractActionsRequest(BaseModel):
    content: str
    model: Optional[Model] = None

class RewriteToneRequest(BaseModel):
    content: str
    target_tone: str                  # e.g. "casual", "formal", "eli5"
    model: Optional[Model] = None

class ProofreadRequest(BaseModel):
    content: str
    model: Optional[Model] = None

class GenerateTestsRequest(BaseModel):
    content: str                      # the function/code
    language: Optional[str] = None
    framework: Optional[str] = None   # e.g. "pytest", "jest"
    model: Optional[Model] = None
```

---

## 3. Add prompt pairs

**File:** `packages/server/src/mindloom/models.py`

### 3a. `Prompts` class — user message prefixes

```python
summarize: str = (
    "Summarize the following text concisely, preserving all key points."
)
translate: str = (
    "Translate the following text accurately, preserving tone and meaning."
)
explain_code: str = (
    "Explain the following code in plain English. Describe what it does, "
    "why, and any notable patterns or pitfalls."
)
commit_message: str = (
    "Generate a concise conventional-commit message for the following diff. "
    "Use the format: type(scope): description."
)
extract_actions: str = (
    "Extract all action items and key points from the following text "
    "as a structured bullet-point list."
)
rewrite_tone: str = (
    "Rewrite the following text in the requested tone while preserving "
    "all original meaning and information."
)
proofread: str = (
    "Proofread the following text. For each issue found, quote the original "
    "phrase, suggest the correction, and briefly explain why."
)
generate_tests: str = (
    "Generate unit test stubs for the following code. Cover happy paths, "
    "edge cases, and error conditions."
)
```

### 3b. `get_user_message` — extend the `prefixes` dict

For endpoints with extra fields (e.g. `target_language`, `target_tone`), the caller in `app.py` should interpolate those into `content` before calling `_run_task`. The `get_user_message` function itself stays generic.

### 3c. `get_system_message` — extend the `directives` dict

```python
EthemeralTaskType.SUMMARIZE: (
    "Act as a Research Assistant. Produce clear, faithful summaries. "
    "Never invent information not present in the source."
),
EthemeralTaskType.TRANSLATE: (
    "Act as a Professional Translator. Preserve meaning, tone, and "
    "formatting. Flag any ambiguous phrases."
),
EthemeralTaskType.EXPLAIN_CODE: (
    "Act as a Patient Senior Developer. Explain code clearly for "
    "someone unfamiliar with the codebase."
),
EthemeralTaskType.COMMIT_MESSAGE: (
    "Act as a meticulous open-source maintainer. Write commit messages "
    "that are concise, descriptive, and follow conventional-commits."
),
EthemeralTaskType.EXTRACT_ACTIONS: (
    "Act as a Project Manager. Identify every actionable item and "
    "decision. Use clear, imperative bullet points."
),
EthemeralTaskType.REWRITE_TONE: (
    "Act as a Versatile Copywriter. Match the requested tone exactly "
    "while keeping all facts intact."
),
EthemeralTaskType.PROOFREAD: (
    "Act as a Strict Proofreader. List issues with quoted originals "
    "and corrections. Do NOT rewrite the whole text."
),
EthemeralTaskType.GENERATE_TESTS: (
    "Act as a QA Engineer. Write idiomatic test code using the "
    "specified framework. Include descriptive test names."
),
```

---

## 4. Add endpoints

**File:** `packages/server/src/mindloom/app.py`

Each endpoint follows the exact same pattern as the existing ones (`create_job` → `_run_task` → `update_job_status`). For endpoints with extra request fields, prepend the metadata to `content` before passing to `_run_task`.

| Route                  | Method | Request Model           | Task Type            |
|------------------------|--------|-------------------------|----------------------|
| `/summarize`           | POST   | `SummarizeRequest`      | `SUMMARIZE`          |
| `/translate`           | POST   | `TranslateRequest`      | `TRANSLATE`          |
| `/code/explain`        | POST   | `ExplainCodeRequest`    | `EXPLAIN_CODE`       |
| `/git/commit-message`  | POST   | `CommitMessageRequest`  | `COMMIT_MESSAGE`     |
| `/extract/actions`     | POST   | `ExtractActionsRequest` | `EXTRACT_ACTIONS`    |
| `/rewrite/tone`        | POST   | `RewriteToneRequest`    | `REWRITE_TONE`       |
| `/proofread`           | POST   | `ProofreadRequest`      | `PROOFREAD`          |
| `/code/generate-tests` | POST   | `GenerateTestsRequest`  | `GENERATE_TESTS`     |

### Extra-field handling example (translate)

```python
@app.post("/translate")
async def translate(req: TranslateRequest, db=Depends(get_db)) -> SectionResponse:
    enriched = f"Target language: {req.target_language}\n\n{req.content}"
    job = database.create_job(db, JobCreate(task_type=EthemeralTaskType.TRANSLATE, content=enriched))
    try:
        result = _run_task(EthemeralTaskType.TRANSLATE, enriched, req.model)
        database.update_job_status(db, job.id, Status.COMPLETED, result=result.content)
        return result
    except Exception:
        database.update_job_status(db, job.id, Status.FAILED)
        raise
```

Same pattern for `rewrite/tone` (prepend `Target tone: {req.target_tone}`), `code/explain` (prepend `Language: {req.language}`), and `code/generate-tests` (prepend framework/language).

---

## 5. Update imports in `app.py`

Add all new request models to the import block from `.models`.

---

## 6. Add tests

**File:** `tests/test_new_endpoints.py` (new)

For each endpoint, write at minimum:
- A happy-path test that mocks `chat_ollama` and asserts `SectionResponse` shape
- A test that the job is persisted in the DB with the correct `task_type`
- A test that a failed LLM call sets job status to `FAILED`

Use the same test fixtures/patterns as existing tests.

---

## 7. Update `test_api.sh`

Add curl examples for each new endpoint for manual smoke testing.

---

## Implementation order

1. Models & enums (`models.py`) — single commit
2. Prompt pairs (`models.py`) — same or next commit
3. Endpoints (`app.py`) — one commit
4. Tests — one commit
5. Update `test_api.sh` — one commit
