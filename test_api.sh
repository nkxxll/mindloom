#!/usr/bin/env bash
# test_api.sh — smoke tests for all mindloom API endpoints

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

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
    "model": "qwen3:latest"
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
    "model": "qwen3:latest"
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
    "model": "qwen3:latest"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /file/improve" "$code" 200 "$body"

# ── POST /email/improve ──────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/email/improve" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "hey, just wanted to check in about the project. can we meet sometime this week or next? let me know. thanks",
    "model": "qwen3:latest"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /email/improve" "$code" 200 "$body"

# ── POST /email/write ────────────────────────────────────────────────────────
body=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/email/write" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Key points: request Q3 budget approval from finance team, deadline is Friday, need $15k for cloud infrastructure expansion",
    "model": "qwen3:latest"
  }')
code=$(echo "$body" | tail -1)
body=$(echo "$body")
check "POST /email/write" "$code" 200 "$body"

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
