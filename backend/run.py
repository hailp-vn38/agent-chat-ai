#!/usr/bin/env python
"""
Script to run the FastAPI application.
"""

import os
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()
SRC_DIR = PROJECT_ROOT / "src"

# Change to src directory
os.chdir(SRC_DIR)

# Run uvicorn directly by replacing current process
os.execvp(
    "uvicorn",
    ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"],
)
