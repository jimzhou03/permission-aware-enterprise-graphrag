from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    department_code: str | None = None
    visibility: str = "private"


class DocumentCreate(BaseModel):
    knowledge_base_code: str
    title: str = Field(min_length=2, max_length=255)
    content: str = Field(min_length=10)
    source_label: str = "fictional-enterprise-doc"
    entities: list[str] = []

