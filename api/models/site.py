from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Enum, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base, UTCDateTime
from api.models.enums import ProbeType, SiteStatus

DEFAULT_PROBE_TYPES = [ProbeType.DNS, ProbeType.TCP, ProbeType.HTTPS]
DEFAULT_TCP_PORTS = [80, 443]
DEFAULT_EXPECTED_STATUS_CODES = [200]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Site(Base):
    """A monitored FQDN and its monitoring configuration.

    Only the latest status lives here; historical measurements go to InfluxDB
    under influxdb_tag.
    """

    __tablename__ = "sites"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    fqdn: Mapped[str] = mapped_column(String(253), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(1024), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    influxdb_tag: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    check_interval: Mapped[int | None] = mapped_column(Integer, default=None)
    timeout: Mapped[int | None] = mapped_column(Integer, default=None)
    enabled_probe_types: Mapped[list[str]] = mapped_column(
        JSON, default=DEFAULT_PROBE_TYPES.copy
    )
    http_method: Mapped[str] = mapped_column(String(10), default="GET")
    http_path: Mapped[str] = mapped_column(String(2048), default="/")
    expected_status_codes: Mapped[list[int]] = mapped_column(
        JSON, default=DEFAULT_EXPECTED_STATUS_CODES.copy
    )
    tcp_ports: Mapped[list[int]] = mapped_column(JSON, default=DEFAULT_TCP_PORTS.copy)

    last_status: Mapped[SiteStatus] = mapped_column(
        Enum(SiteStatus, native_enum=False, length=32),
        default=SiteStatus.UNKNOWN,
        index=True,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # Consecutive suspicious rounds. Persisted rather than held in memory so
    # filtering detection survives restarts and works across worker replicas.
    suspicious_streak: Mapped[int] = mapped_column(Integer, default=0)

    # Scheduling and lease state. Workers claim due sites by writing locked_by
    # and locked_until, so exactly one replica checks a site at a time and a
    # crashed worker's sites become claimable again when its lease expires.
    next_check_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, default=None, index=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(64), default=None)
    locked_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime, default=None, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Site {self.fqdn} {self.last_status}>"
