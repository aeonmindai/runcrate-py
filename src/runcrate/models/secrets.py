"""Secret models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Secret(BaseModel):
    """A secret set in the environment: an environment variable every instance and job
    launched there gets. The API returns names only; values are set in the dashboard and
    never shown. A value given for one launch (``env_vars`` on an instance) wins over a
    secret of the same name.
    """

    # Unlike the other models, unknown fields are dropped, so a value can never be read here.
    model_config = ConfigDict(extra="ignore")

    key: str
    """The variable's name, e.g. ``HF_TOKEN``."""
    sensitive: bool = False
    """A sensitive secret's value is hidden in the dashboard too, for everyone."""
    updated_at: Optional[datetime] = None
    """When the value or its settings last changed."""
