import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.devcontainer import router as devcontainer_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.search import router as search_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_health import router as health_router
from app.api.routes_history import router as history_router
from app.api.routes_map import router as map_router
from app.api.routes_ops import router as ops_router
from app.api.routes_results import router as results_router
from app.api.routes_review import router as review_router
from app.api.routes_share import router as share_router
from app.api.routes_webhook import router as webhook_router
from app.api.scout import router as scout_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.security import ContentSizeLimitMiddleware, SecurityHeadersMiddleware
from app.middleware.org_context import OrgContextMiddleware

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
except ImportError:
    sentry_sdk = None
    FastApiIntegration = None
    SqlalchemyIntegration = None

configure_logging(settings.environment)
logger = logging.getLogger(__name__)


def _validate_production_config() -> None:
    """Log warnings for missing critical env vars at startup.

    Only fires in production so dev/test environments stay noise-free.
    """
    if settings.environment != "production":
        return

    if len(settings.atlas_jwt_secret.strip()) < 32:
        raise RuntimeError(
            "ATLAS_JWT_SECRET must be set to a strong random value in production."
        )

    if not settings.redis_url:
        raise RuntimeError(
            "REDIS_URL must be set in production for shared rate limiting."
        )

    if not settings.sentry_dsn:
        raise RuntimeError(
            "SENTRY_DSN must be set in production for error capture."
        )

    if not settings.admin_api_key.strip():
        logger.warning(
            "ADMIN_API_KEY is not set. All /api/ops/* routes will return 404. "
            "Set ADMIN_API_KEY in Railway to enable the ops dashboard."
        )


_validate_production_config()

if settings.sentry_dsn and sentry_sdk:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
elif settings.sentry_dsn:
    logger.warning("SENTRY_DSN is set but sentry_sdk is not installed; continuing without Sentry")

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


app = FastAPI(
    title="Codebase Atlas API",
    description="AI-powered architecture analysis for public GitHub repositories",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(OrgContextMiddleware, jwt_secret=settings.atlas_jwt_secret)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Outermost layer: reject oversized bodies before rate limiting or route handlers run.
app.add_middleware(ContentSizeLimitMiddleware)

app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(results_router)
app.include_router(history_router)
app.include_router(ops_router)
app.include_router(scout_router)
app.include_router(map_router)
app.include_router(review_router)
app.include_router(share_router)
app.include_router(webhook_router)
app.include_router(intelligence_router, prefix="/api")
app.include_router(devcontainer_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(search_router)
