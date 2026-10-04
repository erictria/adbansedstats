from .base import DomainModel
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Player(DomainModel):
    """Player identity; reuse player_id when updating an existing player.

    external_id belongs to the provider, not a jersey number. Keep it as text
    so identifiers with leading zeroes or letters remain intact.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    player_id: UUID = Field(default_factory=uuid4)
    player_name: str = Field(min_length=1, examples=["Rhon Jay Abarrientos"])
    player_short_name: str = Field(min_length=1, examples=["R. Abarrientos"])
    external_id: str = Field(min_length=1, examples=["150"])
    slug: str | None = Field(
        default=None, min_length=1, examples=["rhon-jay-abarrientos"]
    )
    photo_url: HttpUrl | None = Field(
        default=None,
        examples=[
            "https://statsspace01.sgp1.digitaloceanspaces.com/organizer/people/150/photo_L1.png"
        ],
    )
