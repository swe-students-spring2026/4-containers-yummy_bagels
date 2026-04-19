#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 -m pipenv run black app.py tests
python3 -m pipenv run pylint app.py tests/test_app.py tests/test_more_coverage.py
