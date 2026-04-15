"""
Small helper for the legacy Tools shell.

This keeps backend imports in one place and avoids repeating sys.path
manipulation anywhere the compatibility layer needs to reach the
canonical backend implementation.
"""

from importlib import import_module
from pathlib import Path
import sys


def load_backend_module(module_name: str):
    backend_root = Path(__file__).resolve().parents[1] / "backend"
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)
    return import_module(module_name)
