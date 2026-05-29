# Local LLM / Ollama (Optional)

## 1. 默认行为

- 默认：`LLM_MODE=mock`
- 目的：本地可复现、CI 稳定、无外部 API 默认依赖

## 2. 可选启用 Ollama 生成

`.env` 示例：

```env
LLM_MODE=ollama
LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434
LLM_OLLAMA_MODEL=qwen2.5:7b-instruct
```

## 3. 边界说明（必须）

- Ollama 可用于生成或辅助路由。
- Ollama 不决定权限。
- 权限由后端 RBAC/ACL 与 `selected_kb_ids` 决定。
- `selected_kb_ids` 之外内容不会进入 LLM prompt。
- CI 不依赖 Ollama。

## 4. 失败行为

当 Ollama 生成失败时，服务会 fallback 到 mock 生成，保持可用性并在 model 字段可见 fallback 信息。

## 5. 验证方式

- `GET /api/v1/system/retrieval-config` 查看 `generator_mode` 与 router runtime。
- Developer Trace 检查 `generate_answer` 步骤输出模型信息。
