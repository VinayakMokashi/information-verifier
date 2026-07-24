"""Evidence — the internal artifact retrieval hands to adjudication.

Not an LLM-output schema, so optionals/defaults are fine here.
"""
from pydantic import BaseModel


class Source(BaseModel):
    url: str
    title: str
    publisher: str


class Evidence(BaseModel):
    summary: str = ""              # model's synthesis of what the sources say
    sources: list[Source] = []     # de-duplicated, whitelist-restricted
