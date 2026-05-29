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

1. `visitor`：先问公开问题，再问越权问题（应检索前拒绝）
2. `tech_staff`：问技术问题（命中 `tech-internal`），再问销售问题（拒绝）
3. `product_staff`：问产品流程（命中 `product-internal`）
4. `bilingual_admin`：跨部门问题（可访问全部 9 个 KB）
5. 打开 Developer Trace：展示 `allowed_kb_ids -> target_kb_codes -> selected_kb_ids`

## 4. 每个账号问什么

- visitor：
  - 公司公开售后政策是什么？
  - 销售部本季度客户策略是什么？（预期拒绝）
  - 内部流程怎么走？（预期：`clarification_required`，HTTP 200，不检索、不生成）
- tech_staff：
  - 技术部机器人故障诊断流程是什么？
  - 公司内部员工如何申请知识库权限？
  - 销售部本季度客户策略是什么？（预期拒绝）
- product_staff：
  - 产品生产流程是什么？
  - 产品部门内部知识库写的什么？
- bilingual_admin：
  - HR 招人流程是什么？
  - 销售部本季度客户策略是什么？
  - 技术部机器人故障诊断流程是什么？

## 5. 预期结果

- 公开问题：命中 `public-policy`
- 同部门问题：命中对应 `<department>-internal`
- 越权问题：检索前拒绝（`denied=true`, `citations=[]`）
- 不确定问题：返回 `clarification_required`（HTTP 200），不检索、不生成
