import os
import socket
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def default_worker_id() -> str:
    """Identify this replica. On Kubernetes HOSTNAME is the pod name."""
    return os.environ.get("HOSTNAME") or socket.gethostname()


class Settings(BaseSettings):
    """Application configuration, sourced from HEAL_API_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="HEAL_API_",
        env_file=".env",
        extra="ignore",
    )

    # Containers must bind every interface to be reachable from outside the pod.
    host: str = "0.0.0.0"  # nosec B104
    port: int = 8000
    log_level: LogLevel = "INFO"
    debug: bool = False

    environment: str = "development"
    docs_enabled: bool = True
    redoc_enabled: bool = True

    # Browser clients (the dashboard) are blocked by the same-origin policy
    # unless their origin is listed here. Comma-separated; "*" allows any.
    # NoDecode keeps pydantic-settings from JSON-parsing the env value, so the
    # validator below can accept a plain comma-separated list.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    log_json: bool = True

    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    database_host: str = "localhost"
    database_port: int = 3306
    database_name: str = "heal"
    database_user: str = "heal"
    database_password: SecretStr = SecretStr("")

    influxdb_url: str = "http://localhost:8086"
    influxdb_token: SecretStr = SecretStr("")
    influxdb_org: str = "heal"
    influxdb_bucket: str = "heal"

    check_interval: int = Field(default=30, gt=0, description="Seconds between checks.")
    check_timeout: int = Field(
        default=5, gt=0, description="Per-probe timeout in seconds."
    )
    check_retries: int = Field(default=2, ge=0)
    worker_concurrency: int = Field(default=20, gt=0)
    icmp_enabled: bool = False

    worker_id: str = Field(default_factory=default_worker_id)
    shutdown_timeout: float = Field(default=30.0, gt=0)

    # Sites claimed per tick. Larger batches mean fewer round trips; smaller
    # ones spread work more evenly across replicas.
    claim_batch_size: int = Field(default=50, gt=0)
    # A claim expires after this long, so a crashed worker's sites are retried.
    # Must exceed the worst-case duration of one site's checks.
    lease_seconds: int = Field(default=120, gt=0)

    # Outbound requests target user-supplied hostnames, so private ranges stay
    # blocked unless Heal is deliberately deployed for internal monitoring.
    allow_private_targets: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        """Accept a comma-separated list, which is friendlier in a ConfigMap."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field
    @property
    def database_url(self) -> str:
        password = self.database_password.get_secret_value()
        return (
            f"mysql+aiomysql://{self.database_user}:{password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
