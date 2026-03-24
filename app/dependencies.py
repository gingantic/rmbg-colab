"""Shared FastAPI dependencies."""

from functools import lru_cache
from pathlib import Path

from starlette.templating import Jinja2Templates


@lru_cache
def get_templates() -> Jinja2Templates:
    root = Path(__file__).resolve().parent.parent
    return Jinja2Templates(directory=str(root / "templates"))
