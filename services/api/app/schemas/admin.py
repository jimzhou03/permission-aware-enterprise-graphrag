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


class PermissionMatrixUser(BaseModel):
    email: str
    role: str
    department: str | None
    allowed_kb_codes: list[str] = Field(default_factory=list)


class PermissionMatrixRole(BaseModel):
    name: str
    description: str


class PermissionMatrixDepartment(BaseModel):
    code: str
    name: str


class PermissionMatrixKnowledgeBase(BaseModel):
    code: str
    name: str
    scope: str


class PermissionMatrixResponse(BaseModel):
    users: list[PermissionMatrixUser] = Field(default_factory=list)
    roles: list[PermissionMatrixRole] = Field(default_factory=list)
    departments: list[PermissionMatrixDepartment] = Field(default_factory=list)
    knowledge_bases: list[PermissionMatrixKnowledgeBase] = Field(default_factory=list)
