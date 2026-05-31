# Project Pitch

## 30-second version

这是一个本地可复现的权限感知企业 RAG Demo。核心不是模型效果，而是企业知识库中的权限安全问题。系统通过 JWT、RBAC 和知识库 ACL 先计算用户可访问范围，再结合 router 识别问题目标知识库，执行 `selected_kb_ids = allowed_kb_ids ∩ target_kb_ids`，只在交集内检索。无权限内容不会进入 retrieval、答案生成、trace、cache、audit 或 graph projection。

本项目使用 fictional department documents 作为 demo seed data，用于验证权限范围、检索稳定性和 trace，不代表真实企业资料。

## 2-minute architecture explanation

- 前端：React + Vite（只展示权限范围，不决定权限）
- 后端：FastAPI（权限 authority）
- 数据：PostgreSQL + pgvector
- 缓存：Redis permission-scoped cache
- 图投影：Neo4j graph projection
- 安全：JWT / RBAC / ACL + pre-filtering
- 展示：Permission Matrix Visualizer（read-only）
- 可观测：Developer Trace / GraphRAG projection

核心链路：

`User Request -> JWT -> allowed_kb_ids -> router target_kb_codes -> selected_kb_ids = allowed ∩ target -> retrieval or deny -> answer`

## 5-minute demo flow

1. Login as `bilingual_admin@example.local`
2. Open Permission Matrix
3. Explain product_staff allowed and blocked KBs
4. Login as `product_staff@example.local`
5. Ask `公司内部员工如何申请知识库权限？` -> allowed (`company-internal`)
6. Ask `技术部机器人故障诊断流程是什么？` -> denied before retrieval
7. Login as `bilingual_admin@example.local`
8. Open Developer Trace and explain router / selected scope / retrieval status / audit path

## What is implemented

- Pre-filtering RAG
- JWT + RBAC/ACL
- 9 demo accounts
- 9 knowledge bases
- permission matrix API (`GET /api/v1/admin/permission-matrix`)
- read-only permission matrix page
- pytest + permission matrix script tests
- trace / audit / graph projection

## What is not implemented

- production permission admin panel
- enterprise SSO
- production-grade entity disambiguation
- community detection
- real-time permission propagation control plane
- production LLM pipeline

## How to answer common interview questions

1. Pre-filtering 还是 Post-filtering？
   这个项目是 pre-filtering；先求授权交集，再检索。
2. 为什么不用全库检索后过滤？
   全库检索会增加未授权内容进入中间链路的风险（候选、trace、cache）。
3. 权限变化是否需要重算 embedding？
   不需要。embedding 是内容表示；权限在检索入口按用户实时收敛。
4. GraphRAG 是不是完整实体知识图谱？
   不是。当前是权限范围内的轻量图投影与可解释展示。
5. 为什么默认 mock LLM / mock embedding？
   为了本地可复现与 CI 稳定，不把外部模型作为默认依赖。
6. 这个项目适合什么场景？
   适合展示“企业知识问答中的权限安全链路”，不是生产权限管理后台。
