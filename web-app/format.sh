#!/usr/bin/env bash

set -e

python3 -m pipenv run black .
python3 -m pipenv run pylint app.py
