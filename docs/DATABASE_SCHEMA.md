# Database Schema

## 1. PostgreSQL职责

PostgreSQL保存系统事实数据：

- 用户、角色、部门和权限。
- 知识库和ACL。
- 文档、chunk和embedding。
- 问答审计日志。
- 文档导入任务。

## 2. 表设计

### `users`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `email` | varchar | 登录邮箱，唯一 |
| `full_name` | varchar | 显示名称 |
| `password_hash` | varchar | 密码哈希 |
| `role_id` | UUID | 关联 `roles.id` |
| `department_id` | UUID | 关联 `departments.id` |
| `is_active` | boolean | 是否启用 |
| `created_at` | timestamptz | 创建时间 |
| `updated_at` | timestamptz | 更新时间 |

### `roles`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `name` | varchar | `admin`、`hr`、`finance`、`tech`、`visitor` |
| `description` | varchar | 角色说明 |

### `departments`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `code` | varchar | `hr`、`finance`、`tech`、`public` |
| `name` | varchar | 部门名称 |

### `permissions`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `code` | varchar | 权限编码，如 `qa:ask`、`audit:read` |
| `description` | varchar | 权限说明 |

### `role_permissions`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `role_id` | UUID | 关联角色 |
| `permission_id` | UUID | 关联权限 |

### `knowledge_bases`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `code` | varchar | 知识库编码 |
| `name` | varchar | 知识库名称 |
| `description` | text | 知识库说明 |
| `department_id` | UUID | 所属部门 |
| `visibility` | varchar | `public` 或 `private` |
| `version` | integer | 知识库版本 |
| `is_active` | boolean | 是否启用 |

### `knowledge_base_acl`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `knowledge_base_id` | UUID | 关联知识库 |
| `role_id` | UUID | 可选，授权角色 |
| `department_id` | UUID | 可选，授权部门 |
| `access_level` | varchar | `read`、`manage` |

### `documents`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `knowledge_base_id` | UUID | 关联知识库 |
| `title` | varchar | 文档标题 |
| `source_label` | varchar | 虚构来源标识 |
| `version` | integer | 文档版本 |
| `status` | varchar | `active`、`archived` |

### `document_chunks`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `document_id` | UUID | 关联文档 |
| `knowledge_base_id` | UUID | 冗余知识库ID，用于权限过滤 |
| `ordinal` | integer | chunk顺序 |
| `content` | text | chunk文本 |
| `embedding` | vector | pgvector向量 |
| `chunk_metadata` | jsonb | 元数据 |

关键约束：向量检索必须在SQL层使用 `knowledge_base_id IN (:allowed_kb_ids)`。

### `qa_audit_logs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `request_id` | varchar | 请求ID |
| `user_id` | UUID | 用户ID |
| `question` | text | 问题 |
| `answer` | text | 答案或拒绝说明 |
| `denied` | boolean | 是否拒绝 |
| `refusal_reason` | varchar | 拒绝原因 |
| `hit_kb_ids` | jsonb | 命中知识库ID |
| `hit_document_ids` | jsonb | 命中文档ID |
| `hit_chunk_ids` | jsonb | 命中chunk ID |
| `cache_hit` | boolean | 是否缓存命中 |
| `mode` | varchar | `auto`、`rag`、`graphrag` |
| `model` | varchar | 模型名 |
| `latency_ms` | integer | 请求耗时 |
| `created_at` | timestamptz | 创建时间 |

### `ingestion_jobs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `document_id` | UUID | 关联文档 |
| `status` | varchar | 导入状态 |
| `message` | text | 错误或状态信息 |
| `stats` | jsonb | 导入统计 |

## 3. Neo4j图谱设计

### 节点

- `Department`
- `KnowledgeBase`
- `Document`
- `Chunk`
- `Entity`

### 关系

- `Department -[:OWNS_KB]-> KnowledgeBase`
- `KnowledgeBase -[:HAS_DOCUMENT]-> Document`
- `Document -[:HAS_CHUNK]-> Chunk`
- `Chunk -[:MENTIONS]-> Entity`
- `Entity -[:RELATED_TO]-> Entity`

## 4. 权限与图谱关系

Neo4j不是权限事实源。GraphRAG查询前必须已经从PostgreSQL获得授权chunk或授权document，再进入图谱扩展。

