from .base import DomainModel
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Score = Annotated[int, Field(ge=0, strict=True)]


class Game(DomainModel):
    """Game metadata. Team order follows the source, not assumed home/away.

    Period scores are ordered Q1 onward, including overtime when present.
    Preserve the displayed date until its format and timezone are confirmed.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    game_id: UUID = Field(default_factory=uuid4)
    tournament_id: UUID | None = None  # Nullable for existing imports; set for new datasets.
    team_id_1: UUID
    team_id_2: UUID
    external_id: str | None = Field(default=None, min_length=1, examples=["522"])
    tournament: str | None = Field(default=None, min_length=1)
    competition_name: str | None = Field(default=None, min_length=1)
    venue: str | None = Field(default=None, min_length=1)
    scheduled_at: datetime | None = None
    date_time_raw: str | None = Field(default=None, min_length=1)
    status: Literal['scheduled', 'live', 'final', 'postponed', 'cancelled', 'unknown'] = 'unknown'
    period: int | None = Field(default=None, ge=1, strict=True)
    clock: str | None = Field(default=None, pattern=r"^\d+:[0-5]\d$")
    team_1_score: Score | None = None
    team_2_score: Score | None = None
    team_1_period_scores: list[Score] | None = None
    team_2_period_scores: list[Score] | None = None
    source_url: HttpUrl | None = None

    @model_validator(mode="after")
    def distinct_teams(self):
        if self.team_id_1 == self.team_id_2:
            raise ValueError("A game must have two different teams")
        return self
