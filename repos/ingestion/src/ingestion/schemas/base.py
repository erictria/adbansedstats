from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime


class DomainModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    source: str | None = Field(default=None, min_length=1)
    retrieved_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None  # Set by the store on each write.
