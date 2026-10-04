from datetime import date
from typing import Literal
from uuid import UUID, uuid4
from pydantic import Field, model_validator
from .base import DomainModel


class TournamentTeam(DomainModel):
    tournament_id: UUID
    team_id: UUID


class RosterMembership(DomainModel):
    roster_id: UUID = Field(default_factory=uuid4)
    player_id: UUID
    team_id: UUID
    tournament_id: UUID
    valid_from: date
    valid_to: date | None = None
    jersey_number: str | None = Field(default=None, min_length=1)

    @model_validator(mode='after')
    def dates_in_order(self):
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError('valid_to must be on or after valid_from')
        return self


class SourceMapping(DomainModel):
    source: str = Field(min_length=1)
    entity_type: Literal['league', 'tournament', 'team', 'player', 'game']
    external_id: str = Field(min_length=1)
    scope: str = ''  # E.g. tournament slug if provider IDs are only locally unique.
    internal_id: UUID
