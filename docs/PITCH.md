# Permission-Aware Enterprise GraphRAG Pitch

## 1. 30秒项目介绍

这是一个本地可复现的企业权限感知 GraphRAG 演示系统。  
核心不是“回答更像人”，而是“在回答前先做权限求交并可审计”。

权限主链路：

`User Request -> JWT -> allowed_kb_ids -> router target_kb_codes -> selected_kb_ids = allowed ∩ target -> retrieval or deny -> answer`

## 2. 2分钟架构讲解

1. 身份与权限由后端 RBAC/ACL 决定，前端仅展示。
2. router 只做问题分类与目标范围建议，不能扩权。
3. 后端求交 `selected_kb_ids = allowed ∩ target` 后才进入检索。
4. 无交集时检索前拒绝，避免未授权 chunk 进入中间链路。
5. 支持审计日志与 Developer Trace 复盘路径。

## 3. 5分钟演示路径

1. 登录 `bilingual_admin@example.local`。
2. 打开 `Permission Matrix` 展示 9 个账号与 9 个 KB 的只读访问矩阵。
3. 选择 `product_staff@example.local`，解释 allowed / blocked KB。
4. 在问答页提问 company-internal 问题，展示授权命中。
5. 提问 tech-internal 问题，展示 pre-retrieval deny。
6. 切到 Developer Trace，逐步解释 allowed、target、selected。

## 4. 常见追问

Q: 这是不是生产级权限后台？  
A: 不是。当前页面是 read-only permission visualization，不支持权限编辑与审批流。

Q: 前端是否能扩权？  
A: 不能。前端只传请求；最终权限收敛由后端执行。

Q: 为什么不是先检索再过滤？  
A: 企业场景下先检索可能让未授权内容进入候选、trace 或缓存。该项目采用 pre-filtering。

Q: 是否依赖真实 LLM？  
A: 默认不依赖。默认 `LLM_MODE=mock`、`EMBEDDING_MODE=mock`，保证本地与 CI 稳定复现。

## 5. 项目边界

- 这是演示系统，不是生产级权限控制平面。
- 不支持企业 SSO / SCIM / 审批流 / 策略编排。
- 不提供权限编辑、用户创建、角色修改、ACL 写入。
- GraphRAG 当前是轻量图投影，不是生产级实体知识图谱平台。
