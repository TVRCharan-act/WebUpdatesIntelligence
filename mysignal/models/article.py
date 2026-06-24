from pydantic import BaseModel


class Article(BaseModel):

    url: str

    title: str

    markdown: str

    summary: str | None = None