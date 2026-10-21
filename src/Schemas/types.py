from typing import Annotated

from pydantic import AfterValidator, Field


def _reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Text must not contain NUL characters")
    return value


StoredText = Annotated[str, AfterValidator(_reject_nul)]
PostgresId = Annotated[int, Field(ge=1, le=2147483647)]
