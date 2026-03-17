#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/packages/cli"
uv tool install . -e --force
