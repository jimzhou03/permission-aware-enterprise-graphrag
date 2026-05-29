# Local Embedding (Optional)

## 1. 默认行为

- 默认：`EMBEDDING_MODE=mock`
- 目的：避免启动即下载模型，保证离线演示和 CI 稳定

## 2. 启用方式

在 `.env` 设置：

```env
EMBEDDING_MODE=local
LOCAL_EMBEDDING_BACKEND=sentence-transformers
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
```

或使用 Ollama embedding backend：

```env
EMBEDDING_MODE=local
LOCAL_EMBEDDING_BACKEND=ollama
LOCAL_EMBEDDING_MODEL=nomic-embed-text
LOCAL_EMBEDDING_BASE_URL=http://host.docker.internal:11434
```

## 3. 资源要求

- `sentence-transformers`：需要本地 Python 依赖与模型加载内存
- `ollama`：需要本地 Ollama 服务与对应 embedding 模型

## 4. 重新 seed / reindex

切换 embedding 模式或模型后，建议重新构建并重建索引：

```bash
docker compose -f infra/docker-compose.yml --env-file .env down
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

必要时重置卷：

```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

## 5. 检查方式

- `GET /api/v1/system/retrieval-config` 查看 runtime provider/mode
- 运行 `scripts/demo-local-embedding-check.ps1` 或 `scripts/demo-local-embedding-check.sh`

## 6. 错误处理

local embedding 不可用时会 fallback 到 mock，并在 runtime status 中标记 fallback/error；不会改变权限链路。
