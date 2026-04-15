"""
Compatibility wrapper for the standalone Tools app.

The canonical reviewer engine now lives in:
    backend/app/services/reviewer/service.py

Keeping this shim lets older Tools imports keep working without carrying
two separate review implementations that can drift over time.
"""

from .backend_bridge import load_backend_module


_backend_service = load_backend_module("app.services.reviewer.service")

ReviewError = _backend_service.ReviewError
run_review = _backend_service.run_review

__all__ = ["ReviewError", "run_review"]
