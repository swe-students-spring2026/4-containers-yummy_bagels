#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
MONGO_DBNAME="${MONGO_DBNAME:-test_db}"

COVERAGE_BIN="${COVERAGE_BIN:-$SCRIPT_DIR/../.venv/bin/coverage}"

if [[ -t 1 ]]; then
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[0;33m'
  CYAN=$'\033[0;36m'
  RESET=$'\033[0m'
else
  RED=""
  GREEN=""
  YELLOW=""
  CYAN=""
  RESET=""
fi

if [[ ! -x "$COVERAGE_BIN" ]]; then
  echo "${RED}error:${RESET} coverage not found at \`$COVERAGE_BIN\`"
  echo "Create/install deps first, e.g.:"
  echo "  python3 -m venv .venv && ./.venv/bin/pip install -r machine-learning-client/requirements.txt"
  exit 127
fi

echo "${CYAN}==> machine-learning-client: pytest + coverage${RESET}"
set +e
MONGO_URI="$MONGO_URI" MONGO_DBNAME="$MONGO_DBNAME" "$COVERAGE_BIN" run -m pytest
pytest_status=$?
set -e

report="$("$COVERAGE_BIN" report -m)"
echo "$report"

coverage_pct="$(printf '%s\n' "$report" | awk '$1=="TOTAL"{print $4}' | tr -d '%')"
if [[ -z "$coverage_pct" ]]; then
  echo "${YELLOW}warn:${RESET} could not parse TOTAL coverage percent"
fi

if [[ "$pytest_status" -eq 0 ]]; then
  echo "${GREEN}PASS${RESET} tests; ${CYAN}TOTAL COVERAGE${RESET}: ${coverage_pct:-?}%"
else
  echo "${RED}FAIL${RESET} tests (exit ${pytest_status}); ${CYAN}TOTAL COVERAGE${RESET}: ${coverage_pct:-?}%"
  exit "$pytest_status"
fi
