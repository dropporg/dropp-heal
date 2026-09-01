from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.models import ProbeType, SiteStatus
from api.utils.network import FQDN_PATTERN

HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}


class SiteBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    fqdn: str = Field(min_length=1, max_length=253, examples=["arvancloud.ir"])
    description: str | None = Field(default=None, max_length=1024)
    is_active: bool = True
    check_interval: int | None = Field(default=None, gt=0, le=86400)
    timeout: int | None = Field(default=None, gt=0, le=120)
    enabled_probe_types: list[ProbeType] = Field(
        default_factory=lambda: [ProbeType.DNS, ProbeType.TCP, ProbeType.HTTPS]
    )
    http_method: str = "GET"
    http_path: str = "/"
    expected_status_codes: list[int] = Field(default_factory=lambda: [200])
    tcp_ports: list[int] = Field(default_factory=lambda: [80, 443])

    @field_validator("fqdn")
    @classmethod
    def check_fqdn(cls, value: str) -> str:
        value = value.strip().rstrip(".").lower()
        if not FQDN_PATTERN.match(value):
            raise ValueError("must be a valid hostname, without scheme or path")
        return value

    @field_validator("http_method")
    @classmethod
    def check_method(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in HTTP_METHODS:
            raise ValueError(f"must be one of {sorted(HTTP_METHODS)}")
        return value

    @field_validator("tcp_ports")
    @classmethod
    def check_ports(cls, value: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("ports must be between 1 and 65535")
        return value


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    """Every field optional; omitted keys are left unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    is_active: bool | None = None
    check_interval: int | None = Field(default=None, gt=0, le=86400)
    timeout: int | None = Field(default=None, gt=0, le=120)
    enabled_probe_types: list[ProbeType] | None = None
    http_method: str | None = None
    http_path: str | None = None
    expected_status_codes: list[int] | None = None
    tcp_ports: list[int] | None = None


class SiteRead(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    influxdb_tag: str
    last_status: SiteStatus
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SiteList(BaseModel):
    items: list[SiteRead]
    total: int
    page: int
    page_size: int


class ProbeSnapshot(BaseModel):
    """Latest reading for one probe, as shown on a site's status card."""

    success: bool | None = None
    latency_ms: float | None = None
    status_code: int | None = None
    packet_loss_percent: float | None = None
    checked_at: datetime | None = None


class SiteStatusRead(BaseModel):
    site_id: UUID
    fqdn: str
    status: SiteStatus
    last_checked_at: datetime | None
    probes: dict[str, ProbeSnapshot] = Field(default_factory=dict)
