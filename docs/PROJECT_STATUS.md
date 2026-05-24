# Project Status

最后更新：2026-05-24

## 当前状态

- Docker 运行正常：前端 `http://localhost:5173`、后端 `http://localhost:8000/docs`、健康检查 `GET /healthz` 返回 `{"status":"ok"}`。
- 模型模式保持 `LLM_MODE=mock`。
- 未接入 Ollama，未接入外部大模型 API。

## 本阶段（权限矩阵自动化 + 前端演示）完成项

1. 新增权限矩阵自动化脚本：`scripts/test_permission_matrix.py`
   - 自动登录 5 个角色账号。
   - 自动调用 `/auth/me`、`/knowledge-bases`、`/qa/ask`。
   - 自动验证：
     - visitor 问 finance 薪酬必须拒绝。
     - hr 仅 `hr-policy + public-general`。
     - finance 仅 `finance-policy + public-general`。
     - tech 仅 `tech-policy + public-general`。
     - admin 可访问全部知识库。
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

## Swagger Authorize 现状说明

- `Unprocessable Entity` 原因：Swagger OAuth2 Password 流默认提交 `username/password` 表单；项目登录接口定义为 JSON `email/password`。
- 这是文档交互层差异，不影响真实接口可用性。
- 当前优先路径：前端登录 + 自动化脚本，不需要在 Swagger 手工复制 token。

## 安全边界确认

- 权限判断仍由后端 `PermissionService` 确定性代码完成。
- RAG 检索仍先按 `allowed_kb_ids` 过滤。
- 前端不做权限决定，只做展示和请求触发。
