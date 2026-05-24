export type AskMode = "auto" | "rag" | "graphrag";

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  role: string;
  department: string | null;
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface AuthMeResponse {
  user: UserPublic;
  permission_scope: {
    role: string;
    department: string | null;
  };
}

export interface KnowledgeBase {
  id: string;
  code: string;
  name: string;
  description: string;
  department: string | null;
  visibility: string;
  version: number;
}

export interface DemoCase {
  id: string;
  role: string;
  question: string;
  expected: string;
}

export interface Citation {
  kb_id: string;
  kb_code: string;
  kb_name: string;
  document_id: string;
  document_title: string;
  chunk_id: string;
  score: number;
  excerpt: string;
}

export interface GraphPath {
  chunk_id: string;
  path: string[];
  explanation: string;
}

export interface AskResponse {
  request_id: string;
  answer: string;
  denied: boolean;
  refusal_reason: string | null;
  cache_hit: boolean;
  mode: "direct" | "rag" | "graphrag" | "general";
  route: {
    target_department: string | null;
    mode: "direct" | "rag" | "graphrag" | "general";
    requires_rag: boolean;
    need_rag: boolean;
    confidence: number;
    reason: string;
  };
  retrieved_chunks: Citation[];
  citations: Citation[];
  graph_paths: GraphPath[];
}

export interface AuditLog {
  request_id: string;
  user_id: string | null;
  question: string;
  answer: string;
  denied: boolean;
  refusal_reason: string;
  hit_kb_ids: string[];
  hit_document_ids: string[];
  hit_chunk_ids: string[];
  mode: string;
  model: string;
  cache_hit: boolean;
  latency_ms: number;
}
