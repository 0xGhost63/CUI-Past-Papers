#!/usr/bin/env python3
"""
Vercel Serverless Function entry point for Archivist API.
Zero emojis. Zero em dashes.
"""
import sys
from pathlib import Path

# Add project root directory to sys.path so app.py is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import ArchivistHandler


class handler(ArchivistHandler):
    """Vercel serverless HTTP request handler."""
    pass
