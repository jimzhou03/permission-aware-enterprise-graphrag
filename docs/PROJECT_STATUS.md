# Project Status

最后更新：2026-05-25

## 当前状态

- Docker 运行正常：前端 `http://localhost:5173`、后端 `http://localhost:8000/docs`、健康检查 `GET /healthz` 返回 `{"status":"ok"}`。
- 模型模式保持 `LLM_MODE=mock`。
- v0.4.0 已实现 Neo4j GraphRAG 可视化与权限感知图谱接口（status/overview/request-graph）。
- v0.3.0 已实现 Markdown/TXT 文档上传与重建索引（后端 RBAC 严格校验）。
- v0.2.2 已实现 Function Calling Trace（后端受控函数链路追踪，非自治工具调用）。
- v0.2.1 已接入 Ollama Local Router（仅分类/路由，不参与最终答案生成）。
- 未接入外部大模型 API。
- v0.2.0 已实现 PostgreSQL + pgvector SQL 检索路径，并保留 SQLite/不可用环境安全回退。

## 本阶段（v0.4.0 Neo4j GraphRAG Visualization）完成项

1. 后端图谱可观测接口（只读安全）
   - 新增 `GET /api/v1/graph/status`：返回 Neo4j 配置/可用性、同步状态、fallback 模式、安全同步摘要。
   - 新增 `GET /api/v1/graph/overview`：返回当前用户权限范围内的图谱节点/边（KB->Document->Chunk->Entity）。
   - 新增 `GET /api/v1/qa/{request_id}/graph`：返回请求级图路径与节点/边，支持 owner/admin-audit 读取并按当前查看者权限再次过滤。
   - 新增 `POST /api/v1/graph/sync`：管理员写权限触发 PostgreSQL -> Neo4j 同步（Neo4j 不可用时安全回退）。

2. 权限边界与安全约束（保持强化）
   - 图谱可见性完全由后端 RBAC + `allowed_kb_ids` 决定，前端不能扩权。
   - 请求级图接口对未授权查看者不会返回内部 chunk/document/entity 元数据。
   - 图节点只暴露 `metadata_summary`，不返回完整未授权 chunk 内容。
   - Ollama 仍仅用于分类路由，不参与权限判定与最终答案生成。

3. Graph 同步状态与上传联动
   - 上传/重建索引后标记目标 KB `graph_sync_needed`（运行时安全标记）。
   - 同步成功后清理待同步 KB 标记，并在 graph status 中更新 `last_sync_summary`。
   - `System Status` 与 retrieval-config 增加 Neo4j/GraphRAG 运行态字段。

4. 前端可视化与产品导航
   - 新增产品页签：`GraphRAG`（中文为 `GraphRAG 图谱`）。
   - 图谱页包含：Graph Status、Graph Overview（SVG 轻量可视化）、Graph Path Viewer。
   - 节点点击可查看安全元数据；Raw JSON 继续折叠展示。
   - Knowledge Chat 在存在图路径时新增 `查看图路径 / View graph path` 快捷入口。
   - Developer Trace 新增 `GraphRAG追踪` 区块，展示 fallback、graph paths、node/edge 数量与安全说明。

5. 中文本地化修复
   - 中文模式产品导航改为：`知识问答`、`知识库`、`审计日志`、`系统状态`、`开发者追踪`。
   - 同步修正文案：`文档上传`、`文档查看器`、`分块查看器`、`函数调用追踪`、`GraphRAG追踪`。

6. 当前限制（v0.4.0）
   - 图谱可视化仍为可观测性/演示导向，不是生产级图分析 UI。
   - 最终答案生成器默认仍是 `LLM_MODE=mock`。
   - Ollama 仅用于本地路由分类。
   - 外部 LLM API 未启用，MCP 未接入。
   - 文档上传仍仅支持 Markdown/TXT，不支持 PDF/DOCX。

## 本阶段（v0.3.0 Document Upload + Re-indexing）完成项

1. 后端上传与重建索引能力
   - 新增上传接口：`POST /api/v1/knowledge-bases/{kb_id}/documents/upload`。
   - 新增重建索引接口：`POST /api/v1/documents/{document_id}/reindex`。
   - 上传支持 `Markdown/TXT`（`.md/.txt`，`text/markdown`、`text/plain`、`text/x-markdown`）。
   - 上传默认大小限制：`1MB`。
   - 文本解析流程：UTF-8 解码、换行归一化、过量空行压缩、结构保留。

2. 分块、嵌入、存储与版本失效
   - 新增确定性分块器（可配置 `chunk_size` / `overlap`，默认 `1000/150` 字符）。
   - 分块优先保留标题/段落边界，并生成稳定 `ordinal` 顺序。
   - 继续使用本地 deterministic embedding（`embedding_service`），不接外部 embedding API。
   - 上传与重建索引都会写入 `document_chunks` 并更新 KB `version`。
   - 缓存失效策略采用 `kb_version_hash` 变化触发（无需前端参与，不跨角色泄露）。

3. 权限与安全边界
   - 上传/重建索引权限完全由后端决定，前端不参与授权判断。
   - 上传/重建索引要求：
     - 用户对目标 KB 在可见范围内；
     - 且具备后端写权限（当前演示为 `admin:kb:write`）。
   - `bilingual_admin` 可上传/重建；`cn_staff/en_staff/visitor` 默认不可上传。
   - Ollama 仍仅用于路由分类，不参与权限判定和最终答案生成。

4. 审计事件与可观测性
   - 使用现有 `ingestion_jobs` 记录上传/重建索引事件元数据（成功/失败）：
     - actor user
     - target kb
     - document id
     - filename
     - chunk count
     - action (`document_upload` / `document_reindex`)
     - status + error_code（安全错误码）
   - 不落库存储原始文件内容。
   - `System Status` 新增上传与索引能力字段（enabled/max size/supported types/indexing mode）。

5. 前端改造
   - Knowledge Bases 页面新增上传区域（仅有权限用户可见可用）。
   - 支持选择 `.md/.txt` 文件、可选标题、上传后自动刷新文档与 chunks。
   - 文档列表新增 `Re-index` 操作（仅有权限用户可用）。
   - 无权限用户保持只读 Viewer 体验。
   - 修复 Knowledge Chat 布局：消息区固定视口高度并内部滚动，输入区保持可见，避免页面无限拉长。

6. 当前限制（v0.3.0）
   - 仅支持 Markdown/TXT 上传，不支持 PDF/DOCX/图片解析。
   - 最终答案生成仍是 `LLM_MODE=mock`。
   - 外部 LLM API 未启用。
   - MCP 暂未接入。

## 本阶段（v0.2.2 Function Calling Trace）完成项

1. 后端受控函数链路模型
   - QA 主流程新增确定性内部步骤追踪（非外部可调用工具）：
     - `classify_query`
     - `resolve_user_permission_scope`
     - `check_cache`
     - `search_allowed_chunks`
     - `get_graph_paths`
     - `generate_answer`
     - `save_audit_log`
   - 每步包含安全字段：
     - `tool_name`
     - `status` (`success|skipped|denied|error`)
     - `input_summary`
     - `output_summary`
     - `duration_ms`
     - `security_note`
     - `error_code`（仅安全错误码）
     - `order_index`

2. QA / Trace / System Status 联动
   - QA 响应新增 `function_trace_summary`（紧凑摘要，聊天主界面不展开原始工具 JSON）。
   - `GET /api/v1/qa/{request_id}/trace` 新增完整 `function_trace`。
   - `GET /api/v1/system/retrieval-config` 新增安全声明字段：
     - `function_calling_mode=backend-controlled-trace`
     - `llm_autonomous_tool_calling=false`
     - `permission_authority=backend-rbac`

3. 前端可观测性升级
   - Developer Trace 新增 `Function Calling Trace` 区块，按顺序展示步骤状态、输入/输出摘要、耗时、安全说明、错误码。
   - Raw trace JSON 仍保持折叠。
   - Knowledge Chat 继续保持简洁，仅保留 `View function trace` 入口。
   - System Status 新增函数调用安全姿态说明，不改变权限边界归属。

4. 安全边界强化（不变更核心原则）
   - 权限判定仍严格由后端 RBAC/ACL 决定。
   - Ollama 仅参与路由分类，不参与权限判定与工具调用。
   - 前端无法通过 `knowledge_base_codes` 扩权。
   - trace 不暴露未授权 chunk 内容；检索仍先按 `allowed_kb_ids` 收敛。
   - 默认最终答案生成仍为 `LLM_MODE=mock`；未启用外部 LLM API；未接入 MCP；未实现上传。

5. 自动化测试补强
   - 新增 Function Calling Trace 相关后端测试，覆盖：
     - 授权 RAG 请求链路完整性
     - general fallback 跳过检索
     - cache hit 跳过检索/生成
     - 拒绝路径无未授权 chunk 内容
     - visitor/cn_staff/en_staff/bilingual_admin 权限边界与链路一致性
     - 前端选择和 Ollama 路由均不能扩权
   - 既有权限矩阵脚本与阶段性测试保持兼容。

## 本阶段（v0.2.1 Ollama Local Router）完成项

1. 路由模式升级（仅路由，不改权限）
   - 新增 `LOCAL_ROUTER_MODE=rules|ollama`，默认仍是 `rules`。
   - 新增 Ollama 配置：
     - `OLLAMA_BASE_URL`
     - `OLLAMA_ROUTER_MODEL`
     - `OLLAMA_ROUTER_TIMEOUT_SECONDS`
   - `ollama` 模式调用本地 `qwen2.5:0.5b-instruct` 仅做分类：`language/intent/target_department/need_rag/confidence/reason`。

2. 安全回退与稳定性
   - Ollama 超时、不可用、返回非 JSON 或 schema 不合法时，自动安全回退到规则路由。
   - 回退不会影响 RBAC，不会扩展 `allowed_kb_ids`，不会绕过后端权限。

3. QA / Trace / System Status 可观测性增强
   - QA 响应新增路由元数据：`router_mode`、`router_model`、`router_fallback_used`、`router_error`。
   - Trace 新增路由链路字段：`router_availability`、`router_decision` 等。
   - `GET /api/v1/system/retrieval-config` 新增路由运行态字段：
     - `router_model`
     - `router_availability`
     - `router_fallback_last`
     - `router_error_last`
   - 前端 `System Status` 与 `Developer Trace` 已展示路由步骤与回退状态。

4. 权限边界保持不变
   - 权限判定仍由后端 RBAC 确定性执行。
   - 检索仍先按 `allowed_kb_ids` 收敛，再执行 pgvector SQL / fallback 检索。
   - visitor/cn_staff/en_staff/bilingual_admin 权限矩阵不变。

## 本阶段（v0.2.0 Real pgvector SQL Retrieval）完成项

1. 检索引擎升级（后端）
   - `rag_service` 新增运行时检索引擎判定：
     - `pgvector_sql`
     - `python_cosine_fallback`
   - PostgreSQL 且 `pgvector` 扩展可用、并且配置启用时，走 SQL 向量检索路径。
   - SQLite 或 pgvector 不可用时，自动回退到 Python cosine 路径。

2. 安全约束保持不变（核心）
   - SQL 向量检索在查询层就包含 `knowledge_base_id IN allowed_kb_ids` 约束。
   - 不存在“全局召回后再过滤”的路径。
   - 前端 `knowledge_base_codes` 仍只可收缩范围，不可扩权。
   - 缓存 key 继续按用户/角色/部门/权限范围隔离，并加入检索引擎 token，避免跨引擎污染。

3. 可观测性与 trace 更新
   - `GET /api/v1/system/retrieval-config` 现在返回真实运行态：
     - `retrieval_engine`
     - `top_k`
     - `pgvector_available`
     - `sql_vector_search_enabled`
   - `GET /api/v1/qa/{request_id}/trace` 新增 `retrieval_engine` 字段。
   - 前端 `System Status` 与 `Developer Trace` 已展示检索引擎信息。

4. 文档与限制声明更新
   - README 已改为“PostgreSQL 优先 pgvector SQL、其他环境回退 Python cosine”的真实描述。
   - 保持限制：`LLM_MODE=mock`、确定性 mock embedding、未接 Ollama、未启用外部 LLM、未实现上传流程。

## 本阶段（v0.1.8 Knowledge Base Viewer + Chunk Viewer + Retrieval Trace）完成项

1. 后端只读可观测接口（权限复核）
   - `GET /api/v1/knowledge-bases`：返回当前用户可见知识库，补充 `display_name`、`language` 字段。
   - `GET /api/v1/knowledge-bases/{kb_id}/documents`：仅在调用者有该 KB 访问权限时返回文档列表。
   - `GET /api/v1/documents/{document_id}/chunks`：仅在调用者有文档所属 KB 权限时返回 chunk 详情。
   - `GET /api/v1/qa/{request_id}/trace`：返回结构化 RAG trace，并对 chunk 内容按当前查看者权限再次过滤。
   - `GET /api/v1/system/retrieval-config`：返回安全检索配置（mock embedding、Python cosine similarity MVP、router/generator mode 等）。

2. 前端产品化可观测视图增强
   - Knowledge Bases 页面升级为：知识库列表 + 文档浏览器 + chunk 浏览器。
   - Chunk Viewer 展示：`chunk_index`、`chunk_id`、内容预览、embedding 状态、embedding 维度，完整内容折叠展开。
   - Knowledge Chat 在引用区展示 `chunk_id`，并新增 `View trace` 快捷入口。
   - Developer Trace 页面改为结构化“最新检索链路”展示，并保留折叠的 `Raw trace JSON`。
   - System Status 页面增加检索配置卡片（embedding/retrieval/top_k/pgvector/cache backend）与当前会话状态。

3. 安全边界保持不变
   - 未改动 RBAC 主逻辑，未放宽权限检查。
   - 仍保持 `allowed_kb_ids` 先过滤再检索 chunk。
   - 仍保持 `LLM_MODE=mock`，未接入 Ollama，未接入外部 LLM API。
   - 未引入 MCP，未实现真实文档上传，未启用生产级 pgvector SQL 检索路径。

4. 测试与验证
   - 后端：`docker compose exec -T api python -m pytest -q` 通过（`21 passed`）。
   - 前端：`npm run build` 通过。
   - 权限矩阵：`python scripts/test_permission_matrix.py --base-url http://127.0.0.1:8000` 通过（`8/8 PASS`）。

## 本阶段（v0.1.6 双语部门知识隔离）完成项

1. 后端种子数据与权限矩阵更新
   - 新增演示账号：`cn_staff`、`en_staff`、`bilingual_admin`、`visitor`。
   - 新增知识库：`cn-public`、`cn-internal`、`en-public`、`en-internal`、`public-policy`。
   - ACL 显式绑定角色到知识库，权限仍由后端确定性代码执行。

2. 双语虚构文档入库
   - 中文知识库只包含中文文档。
   - 英文知识库只包含英文文档。
   - `public-policy` 仅包含 visitor-safe 公共信息，不含薪酬/工资/定价/财务敏感内容。

3. 前端演示补强
   - 登录演示账号切换改为新账号集合。
   - 会话区继续展示当前用户、角色、可访问知识库。
   - 新增提示：访问范围由后端 `allowed_kb_ids` 决定，前端不做权限过滤。
   - 安全测试场景保持默认折叠。

4. 自动化测试更新
   - `pytest` 用例迁移到双语隔离矩阵。
   - `scripts/test_permission_matrix.py` 更新为新账号和新知识库校验：
     - `visitor` 问 finance 薪酬仍必须拒绝；
     - `cn_staff`/`en_staff` 跨语言问题必须被拒绝或至少不返回越权 chunk；
     - `bilingual_admin` 可检索中英文知识。

## 本阶段（权限矩阵自动化 + 前端演示）完成项

1. 新增权限矩阵自动化脚本：`scripts/test_permission_matrix.py`
   - 自动登录 4 个角色账号（`cn_staff`、`en_staff`、`bilingual_admin`、`visitor`）。
   - 自动调用 `/auth/me`、`/knowledge-bases`、`/qa/ask`。
   - 自动验证：
     - visitor 问 finance 薪酬必须拒绝。
     - cn_staff 仅 `cn-public + cn-internal`。
     - en_staff 仅 `en-public + en-internal`。
     - bilingual_admin 可访问中英文知识库与 `public-policy`。
   - 失败时打印接口、账号、问题和返回内容，并返回非零退出码。

2. 前端演示增强
   - 登录区支持演示账号下拉，一键切换并自动填充账号密码。
   - 增加越权演示问题按钮（4 个预置场景）。
   - 页面展示当前用户、角色、可访问知识库、本次是否拒绝、命中知识库、审计 `request_id`。

## 本阶段（前端中英文 UI 切换）完成项

1. 前端页面新增语言切换控件：`中文 / English`。
2. 默认语言为中文。
3. 语言选择保存在 `localStorage`，刷新后保持。
4. 已覆盖登录、会话信息、提问区、结果区、审计区、越权演示按钮等核心文案。
5. 越权演示按钮支持中英文显示，但发送给后端的问题文本保持不变，不影响权限矩阵测试。
6. 未修改后端 API、未修改权限判断逻辑、未修改权限矩阵脚本。

## 本阶段（前端视觉重构）完成项

1. UI 重构为“顶部导航 + 左中右控制台”布局：
   - 顶部：项目名称、语言切换、登录身份状态
   - 左侧：账号切换、越权演示场景卡片
   - 中间：提问区、最新响应
   - 右侧：权限范围、命中知识库、请求详情与审计
2. 视觉风格升级为极简科技控制台：浅灰背景、细边框、大圆角、轻阴影、留白更充分。
3. 越权场景按钮升级为卡片式交互；知识库展示为 tag/badge。
4. denied 状态增加风险提示样式（红色风险徽标与提示面板）。
5. 保持中英文 UI 切换、API 调用逻辑、后端权限/RAG/缓存/审计逻辑不变。

## 本阶段（产品化登录体验与主界面重构）完成项

1. 登录体验改造
   - 未登录仅展示企业登录页（产品定位 + 核心能力 + 登录表单）。
   - 登录成功后进入主控制台，不再显示登录表单。
   - 登录态持久化 `localStorage`（token + user）；刷新后调用 `/auth/me` 尝试恢复。
   - 新增 `Logout`，退出后清理本地会话并返回登录页。

2. 主控制台重构
   - 顶部导航：项目名、语言切换、身份 badge、Logout。
   - 左侧：当前用户、当前角色、可访问知识库、Router/Generator 状态占位。
   - 中间：提问区、最新响应、引用片段。
   - 右侧：request_id、拒绝状态、命中知识库、审计详情。

3. 安全测试场景折叠
   - 越权演示入口迁移到 `Security Test Scenarios` 折叠面板。
   - 默认折叠，展开后显示四个安全测试场景。
   - 不影响正常问答主流程。

4. 普通问候 general fallback
   - 后端新增轻量问候意图识别：`你好/hello/hi/早上好/good morning`。
   - 问候命中时返回 `mode=general`、`need_rag=false`、`retrieved_chunks=[]`、`denied=false`。
   - 不进入 RAG 检索，且仍记录审计日志。
   - 当前模型仍为 `mock`，Ollama 与外部模型 API 暂不接入。

## Swagger Authorize 现状说明

- `Unprocessable Entity` 原因：Swagger OAuth2 Password 流默认提交 `username/password` 表单；项目登录接口定义为 JSON `email/password`。
- 这是文档交互层差异，不影响真实接口可用性。
- 当前优先路径：前端登录 + 自动化脚本，不需要在 Swagger 手工复制 token。

## 安全边界确认

- 权限判断仍由后端 `PermissionService` 确定性代码完成。
- RAG 检索仍先按 `allowed_kb_ids` 过滤。
- 前端不做权限决定，只做展示和请求触发。
