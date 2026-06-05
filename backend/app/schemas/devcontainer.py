"""Pydantic schemas for devcontainer + audit APIs."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# DEVCONTAINER SCHEMAS
# ============================================================================


class DevcontainerFeature(BaseModel):
    """Individual devcontainer feature."""

    name: str = Field(..., description="Feature name (e.g., 'python:3.11')")
    version: Optional[str] = Field(None, description="Feature version")


class DevcontainerService(BaseModel):
    """Service configuration (postgres, redis, etc)."""

    name: str = Field(..., description="Service name")
    image: str = Field(..., description="Docker image")
    ports: Optional[dict[str, int]] = Field(None, description="Port mappings")


class DevcontainerConfig(BaseModel):
    """Full devcontainer.json structure."""

    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Base image")
    features: list[str] = Field(default_factory=list, description="Features to install")
    services: dict[str, Any] = Field(default_factory=dict, description="Services (docker-compose)")
    postCreateCommand: Optional[str] = Field(None, description="Command to run after creation")
    customizations: dict[str, Any] = Field(default_factory=dict, description="IDE customizations")
    mounts: list[str] = Field(default_factory=list, description="Volume mounts")
    remoteUser: str = Field(default="vscode", description="Remote user")


class DevcontainerRequest(BaseModel):
    """Request to generate a new devcontainer."""

    # Empty list → backend auto-detects from analysis result
    languages: list[str] = Field(default_factory=list, description="Languages (python, node, go, etc)")
    services: list[str] = Field(default_factory=list, description="Services (postgres, redis, etc)")
    features: list[str] = Field(default_factory=list, description="Additional features")
    customize: bool = Field(default=False, description="Allow customization")


class DevcontainerResponse(BaseModel):
    """Response with generated devcontainer."""

    devcontainer_id: str
    job_id: int
    version_number: int
    # Raw devcontainer.json dict — may include LLM-generated fields beyond the base schema
    config: dict[str, Any]
    repo_url: Optional[str] = None
    created_at: datetime


class DevcontainerVersionResponse(BaseModel):
    """Summary of a devcontainer version."""

    version_number: int
    created_at: datetime
    config: dict[str, Any]


class DevcontainerListResponse(BaseModel):
    """List of all versions for a job."""

    job_id: int
    versions: list[DevcontainerVersionResponse]
    latest_version: int


# ============================================================================
# AUDIT LOG SCHEMAS
# ============================================================================


class AuditLogRequest(BaseModel):
    """Log an action (internal use)."""

    action: str = Field(..., description="Action performed")
    resource_type: Optional[str] = Field(None, description="Resource type")
    resource_id: Optional[UUID] = Field(None, description="Resource ID")
    result: str = Field(default="success", description="Result (success, permission_denied, error)")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    details: Optional[dict[str, Any]] = Field(None, description="Additional metadata")


class AuditLogResponse(BaseModel):
    """Audit log entry."""

    id: UUID
    user_id: Optional[str]
    org_id: UUID
    action: str
    resource_type: Optional[str]
    resource_id: Optional[UUID]
    result: str
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated audit log list."""

    logs: list[AuditLogResponse]
    total: int
    offset: int
    limit: int


# ============================================================================
# SEARCH SCHEMAS
# ============================================================================


class SearchQuery(BaseModel):
    """Semantic search query."""

    query: str = Field(..., description="Search query")
    search_type: str = Field(
        default="architecture",
        description="Type of search (architecture, api, framework, dependency)",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max results")


class SearchResult(BaseModel):
    """Single search result."""

    job_id: UUID
    repo_url: str
    score: float = Field(..., ge=0, le=1, description="Similarity score")
    snippet: str = Field(..., description="Matching text snippet")
    chunk_type: str


class SearchResponse(BaseModel):
    """Search results."""

    query: str
    results: list[SearchResult]
    total: int


# ============================================================================
# ADMIN DASHBOARD SCHEMAS
# ============================================================================


class AdminStatsResponse(BaseModel):
    """Admin dashboard statistics."""

    total_analyses: int
    analyses_this_month: int
    avg_time_to_complete: float  # seconds
    top_frameworks: list[str]
    total_devcontainers_generated: int
    audit_events_this_week: int


class AdminAuditLogResponse(BaseModel):
    """Admin view of audit logs."""

    logs: list[AuditLogResponse]
    total: int
    offset: int
    limit: int
