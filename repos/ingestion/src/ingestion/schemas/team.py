from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Team(BaseModel):
    """Team identity; reuse team_id when updating an existing team.

    external_id is a source-specific identifier, not the team's abbreviation.
    Website metadata is optional because not every source provides it.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    team_id: UUID = Field(default_factory=uuid4)
    team_name: str = Field(min_length=1, examples=["Barangay Ginebra San Miguel"])
    external_id: str = Field(min_length=1, examples=["4"])
    slug: str | None = Field(
        default=None, min_length=1, examples=["barangay-ginebra-san-miguel"]
    )
    profile_url: HttpUrl | None = None
    logo_url: HttpUrl | None = None
