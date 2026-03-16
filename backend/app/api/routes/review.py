# Re-export from the canonical module so both import paths work:
#   from app.api.routes_review import router
#   from app.api.routes.review import router
from app.api.routes_review import router  # noqa: F401
