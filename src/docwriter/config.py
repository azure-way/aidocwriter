from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping
import os


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Model selection
    planner_model: str = "gpt-5.2"
    planner_api_version: str | None = "2025-04-01-preview"
    planner_use_responses: bool = True
    reviewer_model: str = "gpt-5.2"
    reviewer_api_version: str | None = "2025-04-01-preview"
    reviewer_use_responses: bool = True
    writer_model: str = "gpt-5.2"
    writer_api_version: str | None = "2025-04-01-preview"
    writer_use_responses: bool = True
    default_length_pages: int = 80

    # OpenAI
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_api_version: str | None = None

    # Azure Service Bus
    sb_connection_string: str | None = None
    sb_queue_name: str = "docwriter-jobs"
    sb_queue_plan: str = "docwriter-plan"
    sb_queue_plan_intake: str = "docwriter-plan-intake"
    sb_queue_intake_resume: str = "docwriter-intake-resume"
    sb_queue_write: str = "docwriter-write"
    sb_queue_review: str = "docwriter-review"
    sb_queue_review_general: str = "docwriter-review"
    sb_queue_review_style: str = "docwriter-review-style"
    sb_queue_review_cohesion: str = "docwriter-review-cohesion"
    sb_queue_review_summary: str = "docwriter-review-summary"
    sb_queue_verify: str = "docwriter-verify"
    sb_queue_rewrite: str = "docwriter-rewrite"
    sb_queue_diagram_prep: str = "docwriter-diagram-prep"
    sb_queue_diagram_render: str = "docwriter-diagram-render"
    sb_queue_finalize_ready: str = "docwriter-finalize-ready"
    sb_topic_status: str = os.getenv("DOCWRITER_DEFAULT_STATUS_TOPIC", "aidocwriter-status")
    sb_status_subscription: str = "console"
    sb_lock_renew_s: float = 900.0
    write_batch_size: int = 5
    review_batch_size: int = 3
    review_style_batch_size: int = 5
    review_cohesion_batch_size: int = 5
    review_summary_batch_size: int = 5
    review_max_prompt_tokens: int = 15000
    review_style_enabled: bool = True
    review_cohesion_enabled: bool = True
    review_summary_enabled: bool = True

    # Behavior
    request_timeout_s: int = 120
    max_section_tokens: int = 2500
    streaming: bool = False

    # Azure Blob Storage
    blob_connection_string: str | None = None
    blob_container: str = "docwriter"
    status_table_name: str = os.getenv("DOCWRITER_STATUS_TABLE", "DocWriterStatus")
    documents_table_name: str = os.getenv("DOCWRITER_DOCUMENTS_TABLE", "DocWriterDocuments")
    company_profiles_table_name: str = os.getenv("DOCWRITER_COMPANY_PROFILES_TABLE", "DocWriterCompanyProfiles")
    auth0_issuer_base_url: str | None = None
    auth0_audience: str | None = None

    # MCP (third-party)
    mcp_base_url: str | None = None
    mcp_token_url: str | None = None
    mcp_client_id: str | None = None
    mcp_client_secret: str | None = None
    mcp_audience: str | None = None
    mcp_access_token: str | None = None
    mcp_resource_company_profile: str = "resources/company.profile"
    mcp_tool_company_query: str = "tools/company.query"

    # OpenTelemetry (optional)
    otlp_endpoint: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        return cls(
            planner_model=env.get("DOCWRITER_PLANNER_MODEL", cls.planner_model),
            planner_api_version=env.get("DOCWRITER_PLANNER_API_VERSION", cls.planner_api_version),
            planner_use_responses=_coerce_bool(env.get("DOCWRITER_PLANNER_USE_RESPONSES"), cls.planner_use_responses),
            reviewer_model=env.get("DOCWRITER_REVIEWER_MODEL", cls.reviewer_model),
            reviewer_api_version=env.get("DOCWRITER_REVIEWER_API_VERSION", cls.reviewer_api_version),
            reviewer_use_responses=_coerce_bool(env.get("DOCWRITER_REVIEWER_USE_RESPONSES"), cls.reviewer_use_responses),
            writer_model=env.get("DOCWRITER_WRITER_MODEL", cls.writer_model),
            writer_api_version=env.get("DOCWRITER_WRITER_API_VERSION", cls.writer_api_version),
            writer_use_responses=_coerce_bool(env.get("DOCWRITER_WRITER_USE_RESPONSES"), cls.writer_use_responses),
            default_length_pages=_coerce_int(env.get("DOCWRITER_DEFAULT_LENGTH_PAGES"), cls.default_length_pages),
            openai_api_key=env.get("OPENAI_API_KEY"),
            openai_base_url=env.get("OPENAI_BASE_URL"),
            openai_api_version=env.get("OPENAI_API_VERSION"),
            sb_connection_string=env.get("SERVICE_BUS_CONNECTION_STRING"),
            sb_queue_name=env.get("SERVICE_BUS_QUEUE_NAME", cls.sb_queue_name),
            sb_queue_plan=env.get("SERVICE_BUS_QUEUE_PLAN", cls.sb_queue_plan),
            sb_queue_plan_intake=env.get("SERVICE_BUS_QUEUE_PLAN_INTAKE", cls.sb_queue_plan_intake),
            sb_queue_intake_resume=env.get("SERVICE_BUS_QUEUE_INTAKE_RESUME", cls.sb_queue_intake_resume),
            sb_queue_write=env.get("SERVICE_BUS_QUEUE_WRITE", cls.sb_queue_write),
            sb_queue_review=env.get("SERVICE_BUS_QUEUE_REVIEW", cls.sb_queue_review),
            sb_queue_review_general=env.get("SERVICE_BUS_QUEUE_REVIEW_GENERAL", env.get("SERVICE_BUS_QUEUE_REVIEW", cls.sb_queue_review_general)),
            sb_queue_review_style=env.get("SERVICE_BUS_QUEUE_REVIEW_STYLE", cls.sb_queue_review_style),
            sb_queue_review_cohesion=env.get("SERVICE_BUS_QUEUE_REVIEW_COHESION", cls.sb_queue_review_cohesion),
            sb_queue_review_summary=env.get("SERVICE_BUS_QUEUE_REVIEW_SUMMARY", cls.sb_queue_review_summary),
            sb_queue_verify=env.get("SERVICE_BUS_QUEUE_VERIFY", cls.sb_queue_verify),
            sb_queue_rewrite=env.get("SERVICE_BUS_QUEUE_REWRITE", cls.sb_queue_rewrite),
            sb_queue_diagram_prep=env.get("SERVICE_BUS_QUEUE_DIAGRAM_PREP", cls.sb_queue_diagram_prep),
            sb_queue_diagram_render=env.get("SERVICE_BUS_QUEUE_DIAGRAM_RENDER", cls.sb_queue_diagram_render),
            sb_queue_finalize_ready=env.get("SERVICE_BUS_QUEUE_FINALIZE_READY", cls.sb_queue_finalize_ready),
            sb_topic_status=env.get("SERVICE_BUS_TOPIC_STATUS", cls.sb_topic_status),
            sb_status_subscription=env.get("SERVICE_BUS_STATUS_SUBSCRIPTION", cls.sb_status_subscription),
            sb_lock_renew_s=_coerce_float(env.get("SERVICE_BUS_LOCK_RENEW_S"), cls.sb_lock_renew_s),
            write_batch_size=_coerce_int(env.get("DOCWRITER_WRITE_BATCH_SIZE"), cls.write_batch_size),
            review_batch_size=_coerce_int(env.get("DOCWRITER_REVIEW_BATCH_SIZE"), cls.review_batch_size),
            review_style_batch_size=_coerce_int(env.get("DOCWRITER_REVIEW_STYLE_BATCH_SIZE"), cls.review_style_batch_size),
            review_cohesion_batch_size=_coerce_int(env.get("DOCWRITER_REVIEW_COHESION_BATCH_SIZE"), cls.review_cohesion_batch_size),
            review_summary_batch_size=_coerce_int(env.get("DOCWRITER_REVIEW_SUMMARY_BATCH_SIZE"), cls.review_summary_batch_size),
            review_max_prompt_tokens=_coerce_int(env.get("DOCWRITER_REVIEW_MAX_PROMPT_TOKENS"), cls.review_max_prompt_tokens),
            review_style_enabled=_coerce_bool(env.get("DOCWRITER_REVIEW_STYLE_ENABLED"), cls.review_style_enabled),
            review_cohesion_enabled=_coerce_bool(env.get("DOCWRITER_REVIEW_COHESION_ENABLED"), cls.review_cohesion_enabled),
            review_summary_enabled=_coerce_bool(env.get("DOCWRITER_REVIEW_SUMMARY_ENABLED"), cls.review_summary_enabled),
            request_timeout_s=_coerce_int(env.get("DOCWRITER_REQUEST_TIMEOUT_S"), cls.request_timeout_s),
            max_section_tokens=_coerce_int(env.get("DOCWRITER_MAX_SECTION_TOKENS"), cls.max_section_tokens),
            streaming=_coerce_bool(env.get("DOCWRITER_STREAM"), cls.streaming),
            blob_connection_string=env.get("AZURE_STORAGE_CONNECTION_STRING"),
            blob_container=env.get("AZURE_BLOB_CONTAINER", cls.blob_container),
            status_table_name=env.get("DOCWRITER_STATUS_TABLE", cls.status_table_name),
            documents_table_name=env.get("DOCWRITER_DOCUMENTS_TABLE", cls.documents_table_name),
            company_profiles_table_name=env.get("DOCWRITER_COMPANY_PROFILES_TABLE", cls.company_profiles_table_name),
            auth0_issuer_base_url=env.get("AUTH0_ISSUER_BASE_URL", cls.auth0_issuer_base_url),
            auth0_audience=env.get("AUTH0_AUDIENCE", cls.auth0_audience),
            mcp_base_url=env.get("MCP_BASE_URL", cls.mcp_base_url),
            mcp_token_url=env.get("MCP_TOKEN_URL", cls.mcp_token_url),
            mcp_client_id=env.get("MCP_CLIENT_ID", cls.mcp_client_id),
            mcp_client_secret=env.get("MCP_CLIENT_SECRET", cls.mcp_client_secret),
            mcp_audience=env.get("MCP_AUDIENCE", cls.mcp_audience),
            mcp_access_token=env.get("MCP_ACCESS_TOKEN", cls.mcp_access_token),
            mcp_resource_company_profile=env.get("MCP_RESOURCE_COMPANY_PROFILE", cls.mcp_resource_company_profile),
            mcp_tool_company_query=env.get("MCP_TOOL_COMPANY_QUERY", cls.mcp_tool_company_query),
            otlp_endpoint=env.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings.from_env(os.environ)
