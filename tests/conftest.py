"""
Pytest configuration and fixtures.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file at the project root
project_root = Path(__file__).parent.parent
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)
