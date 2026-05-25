# Project Status

最后更新：2026-05-24

## 当前状态

- Docker 运行正常：前端 `http://localhost:5173`、后端 `http://localhost:8000/docs`、健康检查 `GET /healthz` 返回 `{"status":"ok"}`。
- 模型模式保持 `LLM_MODE=mock`。
- 未接入 Ollama，未接入外部大模型 API。
- v0.1.6 已实现双语部门知识隔离（`cn_staff / en_staff / bilingual_admin / visitor`）。

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
