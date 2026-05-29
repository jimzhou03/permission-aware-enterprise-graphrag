# Interview Q&A

## 1. 你的项目是 Pre-filtering 还是 Post-filtering？

Pre-filtering。先计算 `allowed_kb_ids`，再与 `target_kb_codes` 求交得到 `selected_kb_ids`，只在交集内检索。

## 2. 为什么不先全库检索再过滤？

因为“先检索后过滤”会增加未授权数据在中间链路暴露风险（候选、prompt、trace、cache、审计）。

## 3. 怎么兼顾召回率和权限安全？

先保安全边界，再在授权范围内做召回优化。必要时走澄清分支而不是强行 public fallback。

## 4. 权限变化是否需要重算 embedding？

通常不需要。权限控制基于 KB/document ACL 范围，不依赖 embedding 重算。

## 5. 当前 GraphRAG 是不是完整实体级知识图谱？

不是。当前是权限范围内 KB/Document/Chunk/Trace 的图投影，带 light entity 信息。

## 6. 是否实现实体消歧和社区聚类？

没有。未实现生产级实体消歧，也未实现社区聚类（如 Louvain/Leiden）。

## 7. Ollama 是否决定权限？

不决定。Ollama 仅可选用于本地路由/生成，权限仍由后端 RBAC/ACL 决定。

## 8. mock LLM/embedding 的原因是什么？

为了本地可复现与 CI 稳定，不把外部 API / 模型下载作为默认启动依赖。

## 9. 后续如何接真实 embedding？

启用 `EMBEDDING_MODE=local`，选择 `sentence-transformers` 或 `ollama` backend，完成 reindex 后验证效果。

## 10. 项目当前边界是什么？

这是安全链路与可观测性优先的工程演示项目，不是生产级权限后台或完整实体知识图谱平台。
