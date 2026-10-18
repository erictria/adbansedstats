"""Inputs shared by tournament-scoped endpoints."""
from uuid import UUID

from pydantic import BaseModel


class TournamentScope(BaseModel):
    tournament_id: UUID
