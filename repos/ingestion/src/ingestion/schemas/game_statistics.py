from .base import DomainModel
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(ge=0, strict=True)]
Percentage = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class BoxScoreStatistics(DomainModel):
    """One player's box score; intended key is (game_id, player_id).

    Missing stats remain None, not zero. Shooting percentages use a 0–100 scale.
    Team totals belong separately and must not be represented as a player.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    game_id: UUID
    team_id: UUID
    seconds_played: Count | None = None
    points: Count | None = None
    offensive_rebounds: Count | None = None
    defensive_rebounds: Count | None = None
    rebounds: Count | None = None
    assists: Count | None = None
    turnovers: Count | None = None
    steals: Count | None = None
    blocks: Count | None = None
    personal_fouls: Count | None = None
    fouls_drawn: Count | None = None
    plus_minus: int | None = Field(default=None, strict=True)
    field_goals_made: Count | None = None
    field_goals_attempted: Count | None = None
    field_goals_percentage: Percentage | None = None
    two_pointers_made: Count | None = None
    two_pointers_attempted: Count | None = None
    two_pointers_percentage: Percentage | None = None
    three_pointers_made: Count | None = None
    three_pointers_attempted: Count | None = None
    three_pointers_percentage: Percentage | None = None
    four_pointers_made: Count | None = None
    four_pointers_attempted: Count | None = None
    four_pointers_percentage: Percentage | None = None
    free_throws_made: Count | None = None
    free_throws_attempted: Count | None = None
    free_throws_percentage: Percentage | None = None

    @model_validator(mode="after")
    def validate_shooting(self):
        for name in ("field_goals", "two_pointers", "three_pointers", "four_pointers", "free_throws"):
            made = getattr(self, f"{name}_made")
            attempted = getattr(self, f"{name}_attempted")
            if made is not None and attempted is not None and made > attempted:
                raise ValueError(f"{name}: made cannot exceed attempted")
        return self


class TeamGameStatistics(BoxScoreStatistics):
    """Official totals, including unattributed team/coach contributions."""


class GameStatistics(BoxScoreStatistics):
    player_id: UUID
    player_name: str | None = Field(default=None, min_length=1)
    jersey_number: str | None = Field(default=None, min_length=1)
    position: str | None = Field(default=None, min_length=1)
    is_starter: bool | None = None
    minutes_raw: str | None = Field(default=None, min_length=1)
    participation_status: Literal['played', 'dnp', 'inactive', 'unknown'] = 'unknown'

    @model_validator(mode='after')
    def nonparticipant_stats(self):
        if self.participation_status in ('dnp', 'inactive'):
            for name in ('seconds_played', 'points', 'rebounds', 'assists', 'steals', 'blocks',
                         'offensive_rebounds', 'defensive_rebounds', 'turnovers',
                         'personal_fouls', 'fouls_drawn', 'plus_minus'):
                if getattr(self, name) not in (None, 0):
                    raise ValueError('Nonparticipants cannot have nonzero statistics')
            for name in ('field_goals', 'two_pointers', 'three_pointers', 'four_pointers', 'free_throws'):
                if any(getattr(self, f'{name}_{suffix}') not in (None, 0) for suffix in ('made', 'attempted', 'percentage')):
                    raise ValueError('Nonparticipants cannot have shooting statistics')
        return self
