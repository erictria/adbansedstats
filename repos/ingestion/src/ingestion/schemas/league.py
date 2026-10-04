from .base import DomainModel
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class League(DomainModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    league_id: UUID = Field(default_factory=uuid4)
    league_name: str = Field(min_length=1, examples=["Philippine Basketball Association"])
    abbreviation: str | None = Field(default=None, min_length=1, examples=["PBA"])
    external_id: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, min_length=1)
    website_url: HttpUrl | None = None
