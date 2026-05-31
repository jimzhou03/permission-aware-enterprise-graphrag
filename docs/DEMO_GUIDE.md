# Demo Guide

## 1. 启动

Windows:

```powershell
copy .env.example .env
.\scripts\demo-up.ps1
```

macOS / Linux:

```bash
cp .env.example .env
bash scripts/demo-up.sh
```

## 2. 登录

推荐账号：

- `visitor@example.local`
- `tech_staff@example.local`
- `product_staff@example.local`
- `bilingual_admin@example.local`

密码：`Passw0rd!123`

## 3. 推荐演示路径

1. 登录 `bilingual_admin@example.local`，打开 `Permission Matrix` 页面。
2. 在矩阵里选择 `product_staff@example.local`。
3. 解释该用户的 `allowed KBs` 与 `blocked KBs`。
4. 切到知识问答，提问“公司内部员工如何申请知识库权限？”（`company-internal`，应允许）。
5. 再提问“技术部机器人故障诊断流程是什么？”（`tech-internal`，应检索前拒绝）。
6. 打开 Developer Trace：展示 `selected_kb_ids = allowed_kb_ids ∩ target_kb_ids`。

## 4. 每个账号问什么

- visitor：
  - 公司公开售后政策是什么？
  - 销售部本季度客户策略是什么？（预期拒绝）
  - 内部流程怎么走？（预期：`clarification_required`，HTTP 200，不检索、不生成）
- tech_staff：
  - Summarize the Robot SDK deployment troubleshooting checklist.
  - 公司内部员工如何申请知识库权限？
  - 销售部本季度客户策略是什么？（预期拒绝）
- product_staff：
  - 公司内部员工如何申请知识库权限？（预期允许，`company-internal`）
  - 技术部机器人故障诊断流程是什么？（预期拒绝）
  - 产品部门内部知识库写的什么？
- bilingual_admin：
  - HR 招人流程是什么？
  - 销售部本季度客户策略是什么？
  - 打开 Developer Trace 和 Permission Matrix 页面解释权限链路。

## 5. 预期结果

- 公开问题：命中 `public-policy`
- 同部门问题：命中对应 `<department>-internal`
- 越权问题：检索前拒绝（`denied=true`, `citations=[]`）
- 不确定问题：返回 `clarification_required`（HTTP 200），不检索、不生成

## 6. Department Knowledge Coverage Demo

`sample_data` 是 fictional demo knowledge base，用于验证权限范围、检索稳定性和 trace，不代表真实企业资料。

推荐问题：

- `tech_staff@example.local`：技术部机器人故障诊断流程是什么？（应命中 `tech-internal`）
- `sales_staff@example.local`：销售部本季度客户策略是什么？（应命中 `sales-internal`）
- `hr_staff@example.local`：HR 招人流程是什么？（应命中 `hr-internal`）
- `product_staff@example.local`：产品生产流程是什么？（应命中 `product-internal`）
- `visitor@example.local`：销售部本季度客户策略是什么？（应检索前拒绝，`citations=[]`）
