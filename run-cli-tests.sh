#!/bin/bash
source ./env-vars.sh
uv sync
uv run pytest tests/ -v
