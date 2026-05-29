# Architecture

## System Modules

- `apps/web`: React 前端（登录、知识问答、审计、系统状态、Developer Trace、GraphRAG 页面）
- `services/api`: FastAPI 后端（鉴权、权限、QA、审计、图谱、上传）
- `infra/docker-compose.yml`: PostgreSQL/Redis/Neo4j/API/Web 一键运行
- `sample_data`: 演示文档
- `scripts`: 启停、健康检查、权限矩阵脚本

## Runtime Components

- 前端：React + TypeScript + Vite
- 后端：FastAPI + SQLAlchemy + Pydantic
- 检索存储：PostgreSQL + pgvector
- 缓存：Redis
- 图投影：Neo4j（不可用时回退本地轻实体投影）

## QA Request Flow

1. `/api/v1/auth/login` 获取 JWT
2. `/api/v1/qa/ask` 发起问题
3. router 产出 `target_kb_codes`（仅分类，不授权）
4. 后端计算 `allowed_kb_ids`
5. 后端求交 `selected_kb_ids = allowed ∩ target`
6. 在 `selected_kb_ids` 内执行 retrieval（SQL 层过滤）
7. 仅使用授权 citation 生成 answer
8. 保存审计记录（命中 kb/doc/chunk id）
9. `/qa/{request_id}/trace` 查看函数链路与安全说明

## Permission Flow

`User Request -> JWT Claims -> RBAC/ACL -> allowed_kb_ids -> router target_kb_codes -> selected_kb_ids -> retrieval -> answer`

关键点：

- Pre-filtering：检索前权限收敛。
- router / LLM / 前端都不能扩权。
- 未授权 chunk 不进入 prompt/answer/trace/cache/audit/graph view。
