# CLI Implementation Plan - Server Endpoint Coverage

## Overview
The Mindloom CLI currently implements 3 endpoints. The server has 17 total endpoints across multiple categories. This plan outlines implementation strategy for the remaining 14 endpoints.

---

## Currently Implemented (✅ 5 endpoints)
- `/health` (GET) → `mindloom health`
- `/jobs` (GET) → `mindloom jobs [id]`
- `/jobs/{job_id}/restart` (POST) → `mindloom restart <id>`
- `/file/improve` (POST) → `mindloom file <path>`
- `/section/improve` (POST) → `mindloom section <path> [--range START:END]`

---

## Implementation Strategy

### Architecture Pattern
Each feature category uses:
1. **Service class** in `packages/cli/src/mindloom_cli/<category>.py` 
   - Handles HTTP requests via httpx
   - Custom exception classes for error handling
   - Typed methods returning domain models

2. **CLI commands** in `packages/cli/src/mindloom_cli/__main__.py`
   - Click decorators (@cli.command, @cli.group)
   - Arguments, options, error handling
   - Output rendering via display.py

3. **Display helpers** in `packages/cli/src/mindloom_cli/display.py`
   - Format and render results (tables, text, etc.)

---

## Remaining Endpoints by Category

### 1️⃣ SECTION OPERATIONS (1 endpoint)
**Status**: 1/2 done
- ✅ `/section/improve` (POST) → CLI command `mindloom section <path> [--range START:END]`
- ⏳ `/section/extend` (POST) → Missing

**Plan**:
- Add `extend_section()` method to `Section` class in section.py
- Add `ExtendSectionError` exception class
- Add `section extend` subcommand with similar interface: `mindloom section extend <path> [--range START:END]`
- Parameters: `file_path`, optional `--range`, optional `--model`

**Files to modify**:
- `packages/cli/src/mindloom_cli/section.py` - Add extend_section method + error class
- `packages/cli/src/mindloom_cli/__main__.py` - Add section extend subcommand

---

### 2️⃣ EMAIL OPERATIONS (2 endpoints)
**Status**: Not implemented

- `/email/improve` (POST) → `mindloom email improve <content>`
- `/email/write` (POST) → `mindloom email write <content>`

**Plan**:
- Create `packages/cli/src/mindloom_cli/email.py`
- Class `Email` with methods:
  - `improve_email(content, model=None) -> str`
  - `write_email(content, model=None) -> str`
- CLI: `mindloom email improve --text <text> [--model MODEL]` or stdin/file input
- CLI: `mindloom email write --text <text> [--model MODEL]` or stdin/file input

**Files to create/modify**:
- Create: `packages/cli/src/mindloom_cli/email.py`
- Modify: `packages/cli/src/mindloom_cli/__main__.py` - Add email group with subcommands

---

### 3️⃣ TEXT OPERATIONS (3 endpoints)
**Status**: Not implemented

- `/summarize` (POST) → `mindloom summarize <content> [--max-length N]`
- `/translate` (POST) → `mindloom translate <content> --target-language <lang> [--source-language <lang>]`
- `/proofread` (POST) → `mindloom proofread <content>`

**Plan**:
- Create `packages/cli/src/mindloom_cli/text.py`
- Class `Text` with methods:
  - `summarize(content, max_length=None, model=None) -> str`
  - `translate(content, target_language, source_language=None, model=None) -> str`
  - `proofread(content, model=None) -> str`
- CLI commands with stdin/file support

**Files to create/modify**:
- Create: `packages/cli/src/mindloom_cli/text.py`
- Modify: `packages/cli/src/mindloom_cli/__main__.py` - Add text group and subcommands

---

### 4️⃣ CODE OPERATIONS (3 endpoints)
**Status**: Not implemented

- `/code/explain` (POST) → `mindloom code explain <content> [--language LANG]`
- `/code/generate-tests` (POST) → `mindloom code tests <content> [--language LANG] [--framework FRAMEWORK]`
- `/git/commit-message` (POST) → `mindloom git commit-message <content>`

**Plan**:
- Create `packages/cli/src/mindloom_cli/code.py`
- Class `Code` with methods:
  - `explain_code(content, language=None, model=None) -> str`
  - `generate_tests(content, language=None, framework=None, model=None) -> str`
- Create `packages/cli/src/mindloom_cli/git.py`
- Class `Git` with method:
  - `generate_commit_message(content, model=None) -> str`
- CLI commands

**Files to create/modify**:
- Create: `packages/cli/src/mindloom_cli/code.py`
- Create: `packages/cli/src/mindloom_cli/git.py`
- Modify: `packages/cli/src/mindloom_cli/__main__.py` - Add code and git groups

---

### 5️⃣ STRUCTURED OPERATIONS (2 endpoints)
**Status**: Not implemented

- `/extract/actions` (POST) → `mindloom extract actions <content>`
- `/rewrite/tone` (POST) → `mindloom rewrite tone <content> --target-tone <tone>`

**Plan**:
- Create `packages/cli/src/mindloom_cli/extract.py`
- Class `Extract` with method:
  - `extract_actions(content, model=None) -> str`
- Create `packages/cli/src/mindloom_cli/rewrite.py`
- Class `Rewrite` with method:
  - `rewrite_tone(content, target_tone, model=None) -> str`
- CLI commands

**Files to create/modify**:
- Create: `packages/cli/src/mindloom_cli/extract.py`
- Create: `packages/cli/src/mindloom_cli/rewrite.py`
- Modify: `packages/cli/src/mindloom_cli/__main__.py` - Add extract and rewrite groups

---

## Implementation Priority

### Phase 1 (Quickest ROI)
1. `/section/extend` - Reuse existing section.py pattern
2. `/email/improve` + `/email/write` - Straightforward endpoints, high user demand

### Phase 2 (Common workflows)
3. `/code/explain` + `/code/generate-tests` - Developer-focused
4. `/git/commit-message` - Git integration
5. `/summarize` + `/translate` + `/proofread` - General text ops

### Phase 3 (Refinement)
6. `/extract/actions` - Structured extraction
7. `/rewrite/tone` - Tone manipulation
8. Polish display, add piping support (stdin → stdout)

---

## Input Handling Strategy

For all new commands, support multiple input methods:
- **Inline**: `--text "..." or --content "..."`
- **File**: `--file path/to/file.txt`
- **Stdin**: Pipe `cat file.txt | mindloom ...`
- **Interactive**: Read from TTY if available

Example:
```bash
# File-based
mindloom email improve --file draft.txt --model mistral

# Inline
mindloom email improve --text "Hello there" --model mistral

# Stdin
echo "Hello there" | mindloom email improve --model mistral
```

---

## Display Strategy

- **Short results** (< 500 chars): Print directly to stdout
- **Long results**: Show summary, offer paging or file save option
- **Structured results** (actions list, proofread issues): Use table format via display.py
- **Errors**: Use click.secho with red/yellow colors

---

## Testing Strategy

1. Unit tests for each service class (httpx mocking)
2. Integration tests with real/mock server
3. CLI tests using Click's test runner
4. Each new endpoint should have 2-3 tests min

---

## Summary

- **Total endpoints**: 17
- **Currently implemented**: 5
- **Remaining**: 12
- **New service classes**: ~6 (`Email`, `Text`, `Code`, `Git`, `Extract`, `Rewrite`)
- **Extensions to existing classes**: 1 (`Section.extend_section()`)
- **Modifications to __main__.py**: Add groups + commands
- **Estimated effort**: 30-45 dev hours depending on polish level
- **Critical path**: Phase 1 (1-2 hours) → Phase 2 (4-5 hours) → Phase 3 (2-3 hours)
