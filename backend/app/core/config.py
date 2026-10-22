"""Application configuration.

All values can be overridden with environment variables or a `backend/.env`
file (see `.env.example`). Nothing secret is hard-coded except a clearly marked
development placeholder for JWT_SECRET.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_domain_list(value: object) -> list[str]:
    """Accepts either a comma-separated string or a JSON array.

    Keeps `.env` friendly for a university administrator:
        UNIVERSITY_EMAIL_DOMAINS=student.edu,cs.student.edu
    and still allows the JSON form the other list settings use.
    """
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            import json

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw.strip("[]").split(",")
            return [str(item) for item in parsed] if isinstance(parsed, list) else []
        raw = raw.replace(";", ",")
        return raw.split(",")
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "AI Online Class Assistant API"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Database ---
    database_url: str = "sqlite:///./data/app.db"

    # --- Auth ---
    jwt_secret: str = "dev-only-change-me-please-generate-a-real-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Uploads ---
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 200

    # --- Institutional email policy ---
    # Comma-separated in .env, e.g. UNIVERSITY_EMAIL_DOMAINS="student.edu,cs.student.edu"
    # Deliberately no domain is baked into the code: the university decides this.
    university_email_domains: Annotated[list[str], NoDecode] = []
    # Development-only exceptions (e.g. the seeded demo account). Keep empty in production.
    dev_allowed_email_domains: Annotated[list[str], NoDecode] = ["example.com"]
    # When True (default) any institutional address is accepted too — e.g.
    # `someone@anywhere.edu`, `someone@cs.uog.edu.pk`, `someone@ox.ac.uk` — while
    # personal providers (gmail.com, outlook.com, yahoo.com, ...) stay refused.
    # Set to false to allow ONLY the exact domains in UNIVERSITY_EMAIL_DOMAINS.
    accept_any_academic_domain: bool = True

    # --- Email verification ---
    # How long a 6-digit code stays valid, and how many wrong tries are allowed
    # before the user must request a new one.
    verification_code_ttl_minutes: int = 15
    verification_max_attempts: int = 5
    verification_resend_cooldown_seconds: int = 60
    # Password-reset links
    password_reset_ttl_minutes: int = 30
    # Base URL of the frontend, used to build the reset link that is emailed.
    public_app_url: str = "http://localhost:5173"

    # --- Email delivery ---
    # console -> the code/link is written to the backend log (development only).
    # smtp    -> really sent through the SMTP server configured below.
    email_backend: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@localhost"
    smtp_from_name: str = "AI Online Class Assistant"
    smtp_use_starttls: bool = True
    # Implicit TLS (SMTPS), typically on port 465. Leave false for STARTTLS/587.
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 15

    # --- ML pipeline ---
    # auto     -> use the real model when its library is installed, else baseline
    # real     -> require the real model, error out if unavailable
    # baseline -> always use the deterministic baseline implementation
    stt_backend: str = "auto"
    whisper_model: str = "base"
    segment_classifier_backend: str = "auto"
    summarizer_backend: str = "auto"

    @field_validator("university_email_domains", "dev_allowed_email_domains", mode="before")
    @classmethod
    def _split_domains(cls, value: object) -> list[str]:
        return [d.lstrip("@").strip().lower() for d in _parse_domain_list(value) if d.strip()]

    @property
    def allowed_email_domains(self) -> list[str]:
        """University domains plus the development-only exceptions, de-duplicated."""
        seen: dict[str, None] = {}
        for domain in [*self.university_email_domains, *self.dev_allowed_email_domains]:
            seen.setdefault(domain, None)
        return list(seen)

    @property
    def exposes_verification_code(self) -> bool:
        """Only the console (development) email backend hands the code back to the
        client. With real SMTP the code must never appear in an API response."""
        return self.email_backend.strip().lower() == "console"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
