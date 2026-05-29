# Security Model

## RBAC / ACL

- 用户先通过 JWT 身份认证。
- 后端根据角色与部门计算 `allowed_kb_ids`。
- KB ACL 在数据库中显式配置，前端无法扩权。

## Router 与权限关系

- router 只输出 `target_kb_codes`（public/company/department/clarification）。
- 权限 authority 不在 router，不在 LLM，不在前端。

## 核心收敛公式

`selected_kb_ids = allowed_kb_ids ∩ target_kb_ids`

- 若 `target_kb_codes` 明确且交集为空：检索前拒绝。
- 若路由不确定（`clarification_required`）且未显式指定 scope：不检索、不生成，返回澄清提示。
- 若用户显式指定 `knowledge_base_codes`：仍与后端 allowed scope 求交，不允许扩权。

## Pre-retrieval deny

- 拒绝发生在 retrieval 之前。
- denied 请求不会产生命中 chunk，`citations` 为空。

## Trace / Cache / Audit / Graph 隔离

- trace 重建时会按当前查看者权限再过滤 chunk 内容。
- cache key 包含角色/部门/权限范围，防止跨角色复用越权答案。
- audit 记录仅持久化安全元数据（命中 id 集合、模式、延迟等）。
- graph overview / graph trace 仅展示当前授权范围内节点边。
