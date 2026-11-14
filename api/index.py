"""Vercel entrypoint: exposes the Flask WSGI app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.app import app  # noqa: E402,F401
