#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 -m pipenv run black client.py scrape_prof.py tests
python3 -m pipenv run pylint client.py scrape_prof.py tests/test_ml.py
