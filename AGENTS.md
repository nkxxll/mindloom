# Mindloom - Agent Guidelines

## Build, Test, Lint Commands
- **Run server**: `uvicorn mindloom.app:app --reload` or `python main.py`
- **Run single test**: `pytest path/to/test.py::TestClass::test_name -v`
- **All tests**: `pytest`
- **Lint/format**: `ruff check .`, `ruff format .`

## Architecture & Structure
- **Framework**: FastAPI + SQLAlchemy + Ollama (LLM integration)
- **Main entry**: `main.py` → uvicorn server on port 8000
- **API routes**: `mindloom/app.py` → `/health` (GET), `/section` (POST)
- **Database**: SQLite (`sql_app.db`) with `Job` model for persistence
- **Models**: Pydantic schemas (`SectionRequest`, `SectionResponse`), SQLAlchemy ORM (`Job`)
- **LLM**: Ollama integration (`ollamatools.py`) with multiple models (Ministral, Qwen, Gemma, Llama)
- **Task types**: `EthemeralTaskType` (FILE, SECTION, SECTION_EXTEND, IMPROVE_EMAIL, WRITE_EMAIL)

## Code Style Guidelines
- **Language**: Python 3.14+, async/await for FastAPI endpoints
- **Imports**: Group by stdlib, third-party, local; use absolute imports within package
- **Typing**: Use type hints throughout (Pydantic + SQLAlchemy for models)
- **Naming**: snake_case for functions/vars, PascalCase for classes, UPPER_CASE for enums
- **Error handling**: Use FastAPI's HTTPException with status codes; log via logging module
- **DB session**: Dependency injection via `Depends(get_db)` for FastAPI routes
- **TODO marker**: Use `# @todo` for incomplete tasks
- **Prompt templates**: Store in `Prompts` model, system messages via `get_system_message(task_type)`
