#!/bin/bash
# Launch Recall-Session from anywhere.
cd "$(dirname "$(readlink -f "$0")")" && exec .venv/bin/python app.py
