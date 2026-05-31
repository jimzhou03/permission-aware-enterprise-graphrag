import type {
  AuthMeResponse,
  AskMode,
  AskResponse,
  AuditLog,
  DocumentIngestionResult,
  DocumentChunk,
  DemoCase,
  GraphOverview,
  GraphStatus,
  KnowledgeBaseDocument,
  KnowledgeBase,
  PermissionMatrixResponse,
  QAGraphTrace,
  RequestTrace,
  RetrievalConfig,
  LoginResponse
} from "./types";

const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000/api/v1";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export async function listKnowledgeBases(token: string): Promise<KnowledgeBase[]> {
  return request<KnowledgeBase[]>("/knowledge-bases", { method: "GET" }, token);
}

export async function fetchAuthMe(token: string): Promise<AuthMeResponse> {
  return request<AuthMeResponse>("/auth/me", { method: "GET" }, token);
}

export async function listKnowledgeBaseDocuments(
  token: string,
  kbId: string
): Promise<KnowledgeBaseDocument[]> {
  return request<KnowledgeBaseDocument[]>(`/knowledge-bases/${kbId}/documents`, { method: "GET" }, token);
}

export async function listDocumentChunks(token: string, documentId: string): Promise<DocumentChunk[]> {
  return request<DocumentChunk[]>(`/documents/${documentId}/chunks`, { method: "GET" }, token);
}

export async function uploadKnowledgeBaseDocument(
  token: string,
  kbId: string,
  file: File,
  title?: string
): Promise<DocumentIngestionResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (title && title.trim()) {
    formData.append("title", title.trim());
  }

  const response = await fetch(`${API_BASE}/knowledge-bases/${kbId}/documents/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: formData
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as DocumentIngestionResult;
}

export async function reindexDocument(token: string, documentId: string): Promise<DocumentIngestionResult> {
  return request<DocumentIngestionResult>(`/documents/${documentId}/reindex`, { method: "POST" }, token);
}

export async function askQuestion(
  token: string,
  question: string,
  mode: AskMode,
  knowledgeBaseCodes: string[]
): Promise<AskResponse> {
  return request<AskResponse>(
    "/qa/ask",
    {
      method: "POST",
      body: JSON.stringify({ question, mode, knowledge_base_codes: knowledgeBaseCodes })
    },
    token
  );
}

export async function getRequestDetail(token: string, requestId: string): Promise<AuditLog> {
  return request<AuditLog>(`/qa/${requestId}`, { method: "GET" }, token);
}

export async function getRequestTrace(token: string, requestId: string): Promise<RequestTrace> {
  return request<RequestTrace>(`/qa/${requestId}/trace`, { method: "GET" }, token);
}

export async function getRequestGraphTrace(token: string, requestId: string): Promise<QAGraphTrace> {
  return request<QAGraphTrace>(`/qa/${requestId}/graph`, { method: "GET" }, token);
}

export async function listDemoCases(): Promise<DemoCase[]> {
  const payload = await request<{ cases: DemoCase[] }>("/demo/overreach-cases", {
    method: "GET"
  });
  return payload.cases;
}

export async function listAuditLogs(token: string): Promise<AuditLog[]> {
  return request<AuditLog[]>("/admin/audit-logs", { method: "GET" }, token);
}

export async function listPermissionMatrix(token: string): Promise<PermissionMatrixResponse> {
  return request<PermissionMatrixResponse>("/admin/permission-matrix", { method: "GET" }, token);
}

export async function getRetrievalConfig(token: string): Promise<RetrievalConfig> {
  return request<RetrievalConfig>("/system/retrieval-config", { method: "GET" }, token);
}

export async function getGraphStatus(token: string): Promise<GraphStatus> {
  return request<GraphStatus>("/graph/status", { method: "GET" }, token);
}

export async function getGraphOverview(token: string): Promise<GraphOverview> {
  return request<GraphOverview>("/graph/overview", { method: "GET" }, token);
}

export async function syncGraph(token: string): Promise<{
  status: string;
  fallback_used: boolean;
  summary: Record<string, string | number | boolean | null>;
}> {
  return request<{ status: string; fallback_used: boolean; summary: Record<string, string | number | boolean | null> }>(
    "/graph/sync",
    { method: "POST" },
    token
  );
}
