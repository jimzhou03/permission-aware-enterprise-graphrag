# GraphRAG Scope

## 当前范围

当前 GraphRAG 更准确的描述是：

- 权限范围内的 `KB / Document / Chunk / Trace / Light Entity` 图投影
- 支持 Neo4j 可视化与不可用时本地 fallback
- 支持请求级 graph trace（基于授权 citations）

## Light semantic 增强

- Entity 节点为轻量抽取结果（非生产级实体工程）
- 关系以结构关系和轻量语义关系为主（如 `CONTAINS`, `HAS_CHUNK`, `MENTIONS`, `RELATED_TO`）
- 权限仍由 document/kb ACL 决定，不由 graph community 决定

## 未实现能力（明确边界）

- 未实现完整实体消歧
- 未实现社区聚类
- 未实现生产级自动关系抽取流水线
- 未实现自动图谱清洗/治理后台
