import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes.intelligence import router as intelligence_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_health import router as health_router
from app.api.routes_history import router as history_router
from app.api.routes_map import router as map_router
from app.api.routes_ops import router as ops_router
from app.api.routes_results import router as results_router
from app.api.routes_review import router as review_router
from app.api.scout import router as scout_router
from app.core.config import settings
from app.core.logging_config import configure_logging

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(results_router)
app.include_router(history_router)
app.include_router(ops_router)
app.include_router(scout_router)
app.include_router(map_router)
app.include_router(review_router)
app.include_router(intelligence_router, prefix="/api")
