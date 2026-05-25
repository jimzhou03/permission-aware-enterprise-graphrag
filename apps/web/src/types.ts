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
  display_name: string;
  name: string;
  language: string;
  description: string;
  department: string | null;
  visibility: string;
  version: number;
}

export interface KnowledgeBaseDocument {
  id: string;
  knowledge_base_id: string;
  knowledge_base_code: string;
  title: string;
  source: string;
  created_at: string;
  chunk_count: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  knowledge_base_id: string;
  knowledge_base_code: string;
  chunk_index: number;
  content_preview: string;
  content: string;
  has_embedding: boolean;
  embedding_dimension: number;
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

export interface TraceRetrievedChunk {
  chunk_id: string;
  kb_id: string;
  kb_code: string;
  kb_name: string;
  document_id: string;
  document_title: string;
  chunk_index: number;
  content_preview: string;
  content: string;
  has_embedding: boolean;
  embedding_dimension: number;
}

export interface RequestTrace {
  request_id: string;
  user_id: string | null;
  user_email: string | null;
  role: string | null;
  department: string | null;
  question: string;
  answer: string;
  mode: string;
  denied: boolean;
  refusal_reason: string;
  allowed_kb_ids: string[];
  allowed_kb_codes: string[];
  hit_kb_ids: string[];
  hit_document_ids: string[];
  hit_chunk_ids: string[];
  retrieved_chunks: TraceRetrievedChunk[];
  retrieval_engine: string;
  cache_hit: boolean;
  model: string;
  latency_ms: number;
  trace_limits: string[];
}

export interface RetrievalConfig {
  embedding_provider: string;
  embedding_dimension: number;
  retrieval_engine: string;
  top_k: number;
  default_top_k: number;
  generator_mode: string;
  router_mode: string;
  pgvector_available: boolean;
  sql_vector_search_enabled: boolean;
  pgvector_sql_retrieval_enabled: boolean;
  pgvector_field_available: boolean;
  cache_backend: string;
  model_mode: string;
}
