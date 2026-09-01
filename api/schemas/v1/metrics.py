from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from api.models import ProbeType
from api.tsdb.queries import Aggregation


class MetricPoint(BaseModel):
    """One plotted sample."""

    time: datetime
    value: float | None


class MetricSeries(BaseModel):
    """One line on a graph: a single field of a single probe over time."""

    probe_type: ProbeType
    field: str
    points: list[MetricPoint] = Field(default_factory=list)


class MetricsRead(BaseModel):
    site_id: UUID
    fqdn: str
    start: str
    end: str
    aggregation: Aggregation
    window: str | None
    series: list[MetricSeries] = Field(default_factory=list)
