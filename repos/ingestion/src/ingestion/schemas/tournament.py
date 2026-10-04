from .base import DomainModel
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Tournament(DomainModel):
    """A league's season or competition, e.g. Season 50 Governors' Cup."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    tournament_id: UUID = Field(default_factory=uuid4)
    league_id: UUID
    tournament_name: str = Field(min_length=1)
    season: str | None = Field(default=None, min_length=1, examples=["50"])
    external_id: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, min_length=1)
    source_url: HttpUrl | None = None
