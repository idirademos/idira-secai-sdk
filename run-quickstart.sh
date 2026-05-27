#!/bin/bash
source ./env-vars.sh
uv sync
cd sdk-quickstart
uv run quickstart.py
