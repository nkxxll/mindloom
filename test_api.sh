#!/usr/bin/env bash
# test_api.sh — smoke tests for all mindloom API endpoints

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
MODEL='ministral-3:latest'

check() {
  local name="$1"
  local http_code="$2"
  local expected="$3"
  local body="$4"
  if [ "$http_code" -eq "$expected" ]; then
    echo -e "${GREEN}PASS${NC} [$http_code] $name"
    ((PASS++))
  else
    echo -e "${RED}FAIL${NC} [$http_code != $expected] $name"
    ((FAIL++))
  fi
  echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
  echo ""
}

# ── GET /health ──────────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" "$BASE_URL/health")
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "GET /health" "$code" 200 "$body"

# ── POST /section/improve ────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/section/improve" \
  -H "Content-Type: application/json" \
  -d '{
    "start": 0,
    "end": 120,
    "content": "the quick brown fox jump over the lazy dog. it were a beautifull day in the forrest.",
    "file_path": "notes/nature.md",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /section/improve" "$code" 200 "$body"

# ── POST /section/extend ─────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/section/extend" \
  -H "Content-Type: application/json" \
  -d '{
    "start": 0,
    "end": 95,
    "content": "Machine learning is transforming how we interact with software.",
    "file_path": "notes/ml_intro.md",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /section/extend" "$code" 200 "$body"

# ── POST /file/improve ───────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/file/improve" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def add(a,b):\n  return a+b\ndef subtract( a, b ):\n    return a -b\n",
    "file_path": "utils/math_helpers.py",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /file/improve" "$code" 200 "$body"

# ── POST /email/improve ──────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/email/improve" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "hey, just wanted to check in about the project. can we meet sometime this week or next? let me know. thanks",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /email/improve" "$code" 200 "$body"

# ── POST /email/write ────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/email/write" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Key points: request Q3 budget approval from finance team, deadline is Friday, need $15k for cloud infrastructure expansion",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /email/write" "$code" 200 "$body"

# ── POST /summarize ──────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Mindloom uses FastAPI and local LLMs to help improve and generate text workflows for developers and writers.",
    "max_length": 35,
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /summarize" "$code" 200 "$body"

# ── POST /translate ──────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Please share the release notes with the team today.",
    "target_language": "German",
    "source_language": "English",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /translate" "$code" 200 "$body"

# ── POST /code/explain ───────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/code/explain" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def is_even(n):\n    return n % 2 == 0",
    "language": "Python",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /code/explain" "$code" 200 "$body"

# ── POST /git/commit-message ─────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/git/commit-message" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "diff --git a/app.py b/app.py\n+@app.post(\"/summarize\")\n+async def summarize(...):\n+    ...",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /git/commit-message" "$code" 200 "$body"

# ── POST /extract/actions ────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/extract/actions" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Action items: 1) finalize roadmap by Thursday, 2) prepare demo, 3) schedule kickoff with ops team.",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /extract/actions" "$code" 200 "$body"

# ── POST /rewrite/tone ───────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/rewrite/tone" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "hey can you send me the numbers asap thanks",
    "target_tone": "formal",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /rewrite/tone" "$code" 200 "$body"

# ── POST /proofread ──────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/proofread" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "The marketing team have finish there draft yestarday.",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /proofread" "$code" 200 "$body"

# ── POST /code/generate-tests ────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/code/generate-tests" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def divide(a, b):\n    return a / b",
    "language": "Python",
    "framework": "pytest",
    "model": "'"$MODEL"'"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /code/generate-tests" "$code" 200 "$body"

# ── GET /jobs ─────────────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" "$BASE_URL/jobs")
code=$(echo "$body" | tail -1)
body=$(echo "$body" | sed '$d')
check "GET /jobs" "$code" 200 "$body"

# ── GET /jobs/{id} — pick first COMPLETED job and fetch its answer ───────────
job_id=$(echo "$body" | jq -r '[.[] | select(.status == "COMPLETED")][0].id // empty')
if [ -n "$job_id" ]; then
  body=$(curl -s -w "\n%{http_code}" "$BASE_URL/jobs/$job_id")
  code=$(echo "$body" | tail -1)
  body=$(echo "$body" | sed '$d')
  check "GET /jobs/$job_id (COMPLETED)" "$code" 200 "$body"
  echo "── Answer ──"
  echo "$body" | jq -r '.result'
  echo ""
else
  echo -e "${RED}SKIP${NC} No COMPLETED job found to fetch"
  ((FAIL++))
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
