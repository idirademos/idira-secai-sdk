#!/bin/bash
# Wrapper that always sources fresh credentials before running secai-cli.
# Usage:  ./run-cli.sh <command> [args...]
# Debug:  SECAI_DEBUG=1 ./run-cli.sh <command> [args...]
source ./env-vars.sh
uv run secai/secai-cli.py "$@"
