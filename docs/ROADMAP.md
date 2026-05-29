# Roadmap

## v0.7.x demo hardening

- 收紧 router fallback，补齐澄清分支（clarification_required）
- 强化 pre-retrieval deny 与 trace 可解释性
- 增强 README / Demo Guide / 面试叙事一致性
- 提供跨平台 demo 启停与健康检查脚本

## v0.8.x optional local embedding / optional local LLM

- 保持默认 `EMBEDDING_MODE=mock`、`LLM_MODE=mock`
- 提供 local embedding / local LLM 的可选启用文档与检查脚本
- 明确失败 fallback 与边界说明

## v0.9.x light semantic GraphRAG

- 在当前 KB/Document/Chunk/Trace 投影上增加轻量实体语义字段
- 明确非生产级能力边界（无实体消歧、无社区聚类）
- 保持权限链路与图展示权限一致

## v1.0 possible production hardening

- 权限后台与审计治理面
- 更完整的数据导入与版本治理
- 可靠性、可观测性、灰度策略增强
- 生产化部署与安全基线完善
