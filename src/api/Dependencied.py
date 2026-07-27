from typing import Annotated
from fastapi import FastAPI, Depends, Query
from pydantic import BaseModel


class PaginationParams(BaseModel):
    page: Annotated[int | None,Query(1,ge=1)]
    per_page: Annotated[int | None,Query(None,ge=1,le=30)]

paginationDep = Annotated[PaginationParams,Depends()]