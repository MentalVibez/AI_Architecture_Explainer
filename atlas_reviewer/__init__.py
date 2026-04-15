"""
Compatibility package for legacy reviewer imports.

Old tests and scripts still reference ``atlas_reviewer.*``. The canonical
implementation now lives under ``app.services.reviewer`` inside ``backend``.

This package makes those imports resolve to the backend reviewer modules so
older callers keep working without maintaining a second implementation tree.
"""

from importlib import import_module
from pathlib import Path
from pkgutil import walk_packages
import sys


_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
_CANONICAL_PACKAGE = "app.services.reviewer"

if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_backend_pkg = import_module(_CANONICAL_PACKAGE)

# Mirror the backend reviewer package path so this behaves like a real package.
__path__ = list(getattr(_backend_pkg, "__path__", []))


def __getattr__(name: str):
    return getattr(_backend_pkg, name)


def _alias_backend_reviewer_submodules() -> None:
    for _, module_name, _ in walk_packages(__path__, prefix=f"{_CANONICAL_PACKAGE}."):
        module = import_module(module_name)
        alias = module_name.replace(_CANONICAL_PACKAGE, __name__, 1)
        sys.modules.setdefault(alias, module)


def _alias_legacy_test_package() -> None:
    try:
        tools_tests = import_module("Tools.tests")
    except ModuleNotFoundError:
        return

    sys.modules.setdefault(f"{__name__}.tests", tools_tests)


_alias_backend_reviewer_submodules()
_alias_legacy_test_package()
