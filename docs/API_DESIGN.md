# API Design

## 1. API约定

- Base URL：`/api/v1`
- 鉴权方式：`Authorization: Bearer <access_token>`
- 请求和响应格式：JSON
- 错误响应使用标准HTTP状态码和结构化错误信息。

## 2. Auth API

### POST `/auth/login`

登录并返回JWT。

请求：

```json
{
  "email": "hr@example.local",
  "password": "demo-password"
}
```

响应：

```json
{
  "access_token": "example.jwt.token",
  "token_type": "bearer",
  "user": {
    "id": "00000000-0000-0000-0000-000000000000",
    "email": "hr@example.local",
    "full_name": "Demo HR User",
    "role": "hr",
    "department": "hr",
    "permissions": ["qa:ask"]
  }
}
```

### GET `/auth/me`

返回当前用户、角色、部门和权限摘要。

## 3. Knowledge Base API

### GET `/knowledge-bases`

只返回当前用户可访问的知识库。

响应：

```json
[
  {
    "id": "00000000-0000-0000-0000-000000000000",
    "code": "hr-policy",
    "name": "HR Policy",
    "description": "Fictional HR policy knowledge base",
    "department": "hr",
    "visibility": "private",
    "version": 1
  }
]
```

## 4. QA API

### POST `/qa/ask`

提交问题。后端先做权限判断，再进入RAG或GraphRAG。

请求：

```json
{
  "question": "访客可以查看财务薪酬制度吗？",
  "mode": "auto",
  "knowledge_base_codes": []
}
```

响应：

```json
{
  "request_id": "qa_20260524_example",
  "answer": "你没有权限访问财务知识库。",
  "denied": true,
  "refusal_reason": "Requested knowledge base is outside allowed scope.",
  "cache_hit": false,
  "mode": "rag",
  "route": {
    "target_department": "finance",
    "mode": "rag",
    "requires_rag": true,
    "confidence": 0.86,
    "reason": "Question mentions finance compensation policy."
  },
  "citations": [],
  "graph_paths": []
}
```

### GET `/qa/{request_id}`

查看单次问答详情，包括引用、图谱路径和审计状态。

## 5. Admin API

### GET `/admin/users`

管理员查看用户列表。

### POST `/admin/knowledge-bases`

管理员创建知识库。

请求：

```json
{
  "code": "finance-policy",
  "name": "Finance Policy",
  "description": "Fictional finance policy knowledge base",
  "department_code": "finance",
  "visibility": "private"
}
```

### POST `/admin/documents`

管理员录入虚构文档。

请求：

```json
{
  "knowledge_base_code": "finance-policy",
  "title": "Fictional Compensation Policy",
  "content": "This is fictional sample content for demonstration only.",
  "source_label": "fictional-enterprise-doc",
  "entities": ["Compensation", "Finance Department"]
}
```

### GET `/admin/audit-logs`

管理员查看问答审计日志。

## 6. Demo API

### GET `/demo/overreach-cases`

返回预设越权演示案例，例如：

- `visitor` 提问财务薪酬制度。
- `hr` 提问财务预算审批。
- `finance` 提问技术发布密钥轮换。

## 7. 权限要求汇总

| API | 鉴权 | 权限 |
| --- | --- | --- |
| `/auth/login` | 否 | 无 |
| `/auth/me` | 是 | 当前用户 |
| `/knowledge-bases` | 是 | 当前用户可访问范围 |
| `/qa/ask` | 是 | `qa:ask` |
| `/qa/{request_id}` | 是 | 本人或 `audit:read` |
| `/admin/*` | 是 | 对应管理员权限 |
| `/demo/overreach-cases` | 是 | 当前用户或公开演示策略 |

