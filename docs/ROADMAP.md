# Roadmap

## Phase 0: 文档和项目边界

目标：

- 明确PRD、架构、安全边界、API设计、数据库设计和开发路线。
- 补齐README、`.gitignore`、`.env.example`。
- 防止后续开发偏离“权限感知GraphRAG”核心目标。

建议提交：

```text
docs: define product architecture and security boundaries
```

## Phase 1: 后端基础能力

目标：

- FastAPI应用入口。
- PostgreSQL连接和SQLAlchemy模型。
- 用户、角色、部门、权限、知识库ACL。
- 登录、JWT、当前用户接口。
- 种子用户和虚构知识库。

可展示结果：

- 不同用户登录后看到不同可访问知识库。

建议提交：

```text
feat(api): add auth rbac and demo knowledge base schema
```

## Phase 2: 权限内RAG

目标：

- 文档切分。
- embedding生成。
- pgvector检索。
- 检索前强制 `allowed_kb_ids` 过滤。
- 问答审计日志。

可展示结果：

- HR用户能查询HR制度。
- visitor询问财务制度被拒绝。

建议提交：

```text
feat(rag): add permission-scoped vector retrieval and audit logs
```

## Phase 3: Redis缓存防越权

目标：

- 实现权限感知缓存key。
- 缓存成功答案和短TTL拒绝结果。
- 缓存命中也写入审计日志。

可展示结果：

- 同一问题在不同角色下不会串缓存。

建议提交：

```text
feat(cache): add permission-aware qa cache keys
```

## Phase 4: GraphRAG

目标：

- 将部门、知识库、文档、chunk、实体同步到Neo4j。
- 基于授权chunk扩展图谱路径。
- 前端展示GraphRAG引用路径。

可展示结果：

- 用户能看到答案引用的文档和实体关系路径。

建议提交：

```text
feat(graph): add neo4j graph retrieval for authorized documents
```

## Phase 5: 前端MVP

目标：

- 登录页。
- 当前用户信息。
- 可访问知识库列表。
- 问答界面。
- 越权演示案例。
- 管理员审计日志页面。

可展示结果：

- 招聘方可以通过浏览器看到完整业务流程。

建议提交：

```text
feat(web): add login qa audit and overreach demo screens
```

## Phase 6: GitHub展示和工程化收尾

目标：

- Docker Compose本地启动。
- 测试命令。
- README截图或GIF。
- 示例数据说明。
- 安全检查。

可展示结果：

- 项目可以上传GitHub并按README复现。

建议提交：

```text
chore: add docker docs tests and github-ready readme
```

